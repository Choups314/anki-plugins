from aqt import *
import aqt
import anki
from aqt.qt import *
from aqt.utils import showInfo
import utils
import coqpyth
from anki.hooks import addHook, wrap
from aqt.editor import Editor
import chapters
import addMatch_ui
import matchSelector_ui
import noteChanger
from anki.utils import splitFields, namedtmp, tmpdir, call
import shutil
import codecs

#######################################################################
# Tables de la base de donnees
#######################################################################

# CREATE TABLE `PATH.nodes` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `noteId`noteIdINTEGER
# );

# CREATE TABLE `PATH.match` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `nodeId`nodeIdINTEGER,
#         `str`strTEXT
# );

# CREATE TABLE `PATH.links` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `matchId`matchIdINTEGER,
#         `noteId`noteIdINTEGER
# );


#######################################################################
# On generalise le code qui va suivre sous forme "d'applications", pour gerer
# plusieurs types de cartes (avec differents comportements)
# Chaque application est configurer dans les dictionnaires suivants
#######################################################################

# Le mid (type de carte)  des cartes a prendre en compte
midFilter = {}

# Pour chaque type de carte, l'index du champs qui indique le chapitre
chapterField = {}

# On propose ou non les matchs (Si non, alors on chaque lien fait reference au
# match par default
useMatchs = {}

# L'edition des liens est on/off par default
defaultOn = {}
currentOnValue = False
currentOnApp = ""

def linksOn():
    global currentApp
    global currentOnApp
    global currentOnValue
    if currentOnApp != currentApp:
        currentOnApp = currentApp
        currentOnValue = defaultOn[currentApp]
    return currentOnValue

# L'application en cours (Chaine vide s'il n'y en a pas)
currentApp = ""

#######################################################################
# Un widget qui permet de selectionner un match
#######################################################################

def addLinkIfNotExists(matchId, noteId):
    if (mw.col.db.execute("""SELECT COUNT(id) FROM `PATH.links`
                WHERE matchId=%d AND noteId=%d"""
                % (matchId, noteId)).fetchone()[0] == 0) :
        mw.col.db.execute("""
            INSERT INTO `PATH.links` (matchId, noteId)
            VALUES (%d, %d)""" % (matchId, noteId))

def addDefault(noteId, targetNoteId):
    nodeId = getNodeId(targetNoteId)
    # On recuperre l'ID du match Default
    defaultMatchId = mw.col.db.execute("""
            SELECT M.id FROM `PATH.match` AS M
                WHERE nodeId=%d LIMIT 1""" % nodeId).fetchone()[0]
    addLinkIfNotExists(defaultMatchId, noteId)


class MatchSelectorModel:
    def __init__(self, ui, noteId):
        self.ui = ui
        self.noteId = noteId[0]
        # Avec cet appel, on est sur que le noeud existe bien
        self.ui.form.matchsList.connect(self.ui.form.matchsList, SIGNAL("doubleClicked(QModelIndex)"), self.onDoubleClicked)
        self.ui.form.edit.connect(self.ui.form.edit, SIGNAL("clicked()"), self.onEdit)
        self.updateList()

    def onEdit(self):
        setMatchs(mw.col.getNote(self.noteId))

    def onDoubleClicked(self, modelIndex):
        row = modelIndex.row()
        # On ajoute le lien (Si il n'est pas deja present) et on reaffiche les
        # liens. Enfin on ferme cette fenettre
        if row == 0: # Si c'est le "Default"
            addDefault(utils.currentNote.id, self.noteId)
        else:
            matchId = self.matchIds[row - 1]
            addLinkIfNotExists(matchId, utils.currentNote.id)
        displayLinks(utils.currentNote.id)
        self.ui.close()

    def updateList(self):
        # En premier on affiche l'item "Default" qui n'est associe a aucun match
        self.ui.form.matchsList.clear()
        self.ui.form.matchsList.addItem("Default")
        self.matchs = []
        self.matchIds = {}
        # On recupere la liste des matchs et on les affiche
        row = 0
        for matchId, s in mw.col.db.execute("""
            SELECT M.id, str FROM `PATH.match` AS M
            JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                                    WHERE noteId=%d""" % (self.noteId)):
            if s == '': continue # Le match "Default"
            self.matchs.append(s)
            self.matchIds[row] = matchId
            row += 1
            self.ui.form.matchsList.addItem(s)

#######################################################################
# On ajoute un widget en haut, qui contiendra les questions (des liens)
#######################################################################

def getNodeId(noteId):
    # On  ajoute un noeud, s'il n'y en a pas deja un, et on lui ajoute un match "Default"
    new = mw.col.db.execute("""SELECT COUNT(id) FROM `PATH.nodes` WHERE noteId = %d""" % (noteId)).fetchone()[0] == 0
    if new:
        mw.col.db.execute("""INSERT INTO `PATH.nodes` (noteId) VALUES (%d)""" % (noteId))
    nodeId = mw.col.db.execute("SELECT id FROM `PATH.nodes` WHERE noteId = %d LIMIT 1" % (noteId)).fetchone()[0]
    if new:
        mw.col.db.execute("""INSERT INTO `PATH.match` (nodeId, str) VALUES (%d, '')""" %  nodeId)
    return nodeId

def onTocClicked(noteId):
    global currentApp
    if currentApp != "":
        if useMatchs[currentApp]:
            utils.displayDialog("matchSelector", matchSelector_ui.Ui_Form, MatchSelectorModel,
                                500, 500, "Match selector", False, noteId)
        else:
            addDefault(utils.currentNote.id, noteId)
            displayLinks(utils.currentNote.id)
            pass

def showQuestion():
    global currentApp
    note = utils.currentNote
    # On scroll le graph
    graphFocusNode(note.id)
    # On verifie que l'on gere cette carte ...
    managed = False
    for app in midFilter:
        if note.mid in midFilter[app]:
            currentApp = app
            utils.sideWidgets["links"].checkAndShow()
            chap = note.fields[chapterField[app][note.mid]]
            # A priori, le sommaire n'est pas encore afifche
            chapters.displayChapter(chap)
            # On affiche les liens
            displayLinks(note.id)
            managed = True
            break
    if not managed:
        # Sinon on reset le widget des liens
        currentApp = ""
        utils.sideWidgets["links"].hide()

addHook("showQuestion", showQuestion)

#######################################################################
# Saisie des matchs
#######################################################################

class SetMatchModel:
    def __init__(self, ui, note):
        self.note = note[0]
        self.nid = self.note.id
        self.ui = ui
        self.ui.form.prev.connect(self.ui.form.prev, SIGNAL("clicked()"), self.onPrev)
        self.ui.form.next.connect(self.ui.form.next, SIGNAL("clicked()"), self.onNext)
        self.ui.form.add.connect(self.ui.form.add, SIGNAL("clicked()"), self.onAdd)
        self.ui.form.remove.connect(self.ui.form.remove, SIGNAL("clicked()"), self.onRemove)
        self.ui.form.content.connect(self.ui.form.content, SIGNAL("textChanged()"), self.onTextChanged)
        # On commence par charger les matchs deja presents
        self.matchs = []
        self.currIndex = 0
        for s in mw.col.db.execute("""
            SELECT str FROM `PATH.match` AS M
            JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                                   WHERE noteId=%d""" % (self.nid)):
            self.matchs.append(s[0])
        # Et on affiche le premier
        if len(self.matchs) <= 0:
            self.matchs.append("")
        self.ui.form.content.setText(self.matchs[0])
        # Et on met a jour le compteur
        self.ui.form.num.setText("1 / " + str(len(self.matchs)))

    def onPrev(self):
        if self.currIndex > 0: self.currIndex = (self.currIndex - 1)
        else: self.currIndex = len(self.matchs) - 1
        self.ui.form.content.setText(self.matchs[self.currIndex])
        self.ui.form.num.setText(str(self.currIndex + 1) + " / " + str(len(self.matchs)))

    def onNext(self):
        self.currIndex = (self.currIndex + 1) % len(self.matchs)
        self.ui.form.content.setText(self.matchs[self.currIndex])
        self.ui.form.num.setText(str(self.currIndex + 1) + " / " + str(len(self.matchs)))

    def onAdd(self):
        self.matchs.append("")
        self.currIndex = len(self.matchs) - 1
        self.ui.form.content.setText("")
        self.ui.form.num.setText(str(self.currIndex + 1) + " / " + str(len(self.matchs)))

    def onRemove(self):
        self.matchs.pop(self.currIndex)
        if(self.currIndex > 0): self.currIndex -= 1
        if len(self.matchs) <= 0:
            self.matchs.append("")
        self.ui.form.content.setText(self.matchs[self.currIndex])
        self.ui.form.num.setText(str(self.currIndex + 1) + " / " + str(len(self.matchs)))

    def onTextChanged(self):
        self.matchs[self.currIndex] = self.ui.form.content.toPlainText()

    def reject(self):
        nodeId = getNodeId(self.nid)
        # On reset tous les match de ce noeud (Sauf le default)
        mw.col.db.execute("DELETE FROM `PATH.match` WHERE nodeId=%d AND NOT (str = '')" % (nodeId))
        for s in self.matchs:
            s = s.strip()
            if s == '': continue
            mw.col.db.execute("INSERT INTO `PATH.match` (nodeId, str) VALUES (%d, '%s')" % (nodeId, s))
        # Si la fenetre de selection de match est ouverte, on met la met a jour
        if "matchSelector" in aqt.dialogs._dialogs.keys():
            inst = aqt.dialogs._dialogs["matchSelector"]
            if not inst[1] is None: inst[1].model.updateList()

def initButton(b):
    b.setText("Set matchs")

def setMatchs(note = None):
    if note is None:
        note = utils.currentNote
    utils.displayDialog("setMatch", addMatch_ui.Ui_Form, SetMatchModel,
            500, 500, "Add match", True, note)

utils.addNoteWidget("noteMatchAdd", QPushButton, "clicked()", setMatchs, initButton)


#######################################################################
# Les differentes actions affichees lors du review d'une carte
######################################################################

# On ajoute notre bouton (lors de l'affichage des cartes dans le reviewer) pour
# definir les match

def addCreateLinksButton(self, m):
    m.addSeparator()
    a = m.addAction("Set matchs")
    a.setShortcut(QKeySequence("Shift+M"))
    a.connect(a, SIGNAL("triggered()"), setMatchs)

addHook("Reviewer.contextMenuEvent", addCreateLinksButton)


#######################################################################
# On affiche les liens de la carte en cours dans un widget a gauche
#######################################################################

def deleteLink(linkId):
    mw.col.db.execute("""DELETE FROM `PATH.links` WHERE id=%d""" % linkId)
    # Et on met a jour l'affichage
    displayLinks(utils.currentNote.id)

def linkHandler(link):
    global currentOnValue
    action = link[:2]
    if action == "su":
        param = int(link[3:])
        deleteLink(param)
    elif action == "of": # Off
        chapters.setTocCallback(None)
        currentOnValue = False
    elif action == "on": # On
        chapters.setTocCallback(onTocClicked)
        currentOnValue = True
    elif action == "go":
        param = int(link[3:])
        noteChanger.changeCard(param, True)

utils.addSideWidget("links", "[PATH] Afficher / cacher les liens.", "Shift+L", linkHandler,
        QSize(450, 100), Qt.LeftDockWidgetArea, loadHeader=True, autoToggle=False)

def displayLinks(noteId):
    global defaultOn
    global currentApp
    links = linksOn()
    html = """<form>
        <div id="radio">
            <input type="radio" id="off" name="radio" %s>
                <label for="off">Off</label>
            <input type="radio" id="on" name="radio" %s>
                <label for="on">On</label>
        </div>
    </form> \n""" % (   "" if links else "checked=\"checked\"",
                        "" if not links else "checked=\"checked\"")
    # On ajoute chaque lien dans un accordeon Jquery
    html += """<div id="accordion">\n"""
    # On les recupere d'abord dans la bdd
    for s, nid, lid in mw.col.db.execute("""SELECT M.str, N.noteId, L.id FROM `PATH.links` AS L
        JOIN `PATH.match` AS M ON M.id = L.matchId
        JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                                    WHERE L.noteId = %d""" % (noteId)):
        label = chapters.getLabel(nid)
        if(label.strip != ""):
            html += "<h3>" + label + "</h3>\n<div>"
            # Traitement special pour le match "Default"
            if s != "":
                html += "<p>%s</p> <br>" % s
            html += """ <button class="b_del" onclick="py.link('su_%s');">Supprimer</button>
                    <button class="b_go" onclick="py.link('go_%s');">Aller</button></div>\n""" % (lid, nid)
    html += "</div>\n"
    JS_update = """
        $(function() {
            $( '#accordion' ).accordion({
                collapsible:true,
                active:false}); });
            $('#radio').buttonset();
            $(".b_del").button({icons: {primary: "ui-icon-closethick"}});
            $(".b_go").button({icons: {primary: "ui-icon-arrowthickstop"}});
            $("input:radio[name=radio]").click(function() {
                var value = $(this).attr("id");
                py.link(value);
            });
    """
    utils.sideWidgets["links"].update("", html, JS=JS_update)


#######################################################################
# Application pour les cartes de cours
#######################################################################

midFilter["Cours"] = [1419157173874, 1421781450069, 1419152687852]
chapterField["Cours"] = {
    1419157173874: 4,
    1421781450069: 5,
    1419152687852: 2
}
useMatchs["Cours"] = False
defaultOn["Cours"] = False


#######################################################################
# Application pour les cartes d'exercice
#######################################################################

midFilter["Exos"] = [1421169816293]
chapterField["Exos"] = {1421169816293 : 1}
useMatchs["Exos"] = True
defaultOn["Exos"] = True


#######################################################################
# Generation des graphs dot
#######################################################################

def exeGenerate():
    generateGraph(
        [1419157173874, 1421781450069, 1419152687852],
        {
            1419157173874: 4,
            1421781450069: 5,
            1419152687852: 2
        }, {
            1419157173874: 3,
            1421781450069: 4,
            1419152687852: 0
        }
    )

genGraph = QAction("[PATHS] Generer le graphe", mw)
mw.connect(genGraph, SIGNAL("triggered()"), exeGenerate)
mw.form.menuTools.addAction(genGraph)

def generateGraph(mids, chaptersField, labelsField):
    """ chapterField and labelField are dictionnaries. """
    output = "digraph G { \n"
    # On ne traite que les chapitres qui ont actives le graphe
    chapts = chapters.graphChapters()
    # le dico nodes contient une liste pour chaque chapitre. Chaque liste
    # contient tous les neuds (un par note) presents dans ce chapitre, et
    # representes par des tuples (noteId, label)
    nodes = {}
    for mid in mids:
        chapterField = chaptersField[mid]
        labelField = labelsField[mid]
        for id, flds in mw.col.db.execute("""
               SELECT id, flds FROM notes WHERE mid=%d
            """ % mid):
            fields = splitFields(flds)
            chapter = fields[chapterField]
            if not chapter in chapts:
                continue
            label = fields[labelField]
            if(not chapter in nodes):
                nodes[chapter] = []
            nodes[chapter].append((id, label))
    # On genere les noeuds, dans des clusters (un par chapitre)
    notes = []
    for chap in nodes:
        output += """subgraph cluster_%d {
            node [style=filled];
            label = "%s";
            color=blue;
        """ % (chapts[chap], chap)
        for n in nodes[chap]:
            output += """n%d [label="%s", URL="%d"];\n""" % (n[0], n[1], n[0])
            notes.append(n)
        output += """
        }\n"""
    # Puis on ajoute tous les liens ..
    for n in notes:
        for nid in mw.col.db.execute("""SELECT N.noteId FROM `PATH.links` AS L
            JOIN `PATH.match` AS M ON M.id = L.matchId
            JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                                        WHERE L.noteId = %d""" % (n[0])):
            output += """n%d -> n%d;\n""" % (nid[0], n[0])
    output += "}"
    generateGraphImage(output)

graphName = "graph.png"
graphMapName = "graphMap.cmapx"

def generateGraphImage(graph):
    # On ecrit le graphe dot dans un fichier temporaire, puis on le genere au
    # format png
    # On genere aussi le map
    graphDotFile = namedtmp("graph.dot")
    graphDot = codecs.open(graphDotFile, "w+", encoding="utf-8")
    graphDot.write(graph)
    graphDot.close()
    log = open(namedtmp("dot_log.txt"), "w")
    mdir = mw.col.media.dir()
    oldcwd = os.getcwd()
    png = str(namedtmp("tmpGraph.png"))
    cmapx = str(namedtmp("tmpGraph.cmapx"))
    cmds = [
        ["dot", graphDotFile, "-Tpng", "-o%s" % png],
        ["dot", graphDotFile, "-Tcmapx", "-Tcmapx", "-o%s" % cmapx]
    ]
    try:
        os.chdir(tmpdir())
        for cmd in cmds:
            if call(cmd, stdout=log, stderr=log):
                # Erreur ..
                log = open(namedtmp("dot_log.txt", rm=False)).read()
                msg = (_("Error generating graph %s.") % (log))
                showInfo(msg)
                break
        # On ajoute l'image et le map dans les medias
        shutil.copyfile(png, os.path.join(mdir, graphName))
        shutil.copyfile(cmapx, os.path.join(mdir, graphMapName))
        showInfo(_("Graph successfully generated !"))
    finally:
        os.chdir(oldcwd)
    updateGraph()

#######################################################################
# On affiche le graphe dans un side-widget
#######################################################################

def graphLinkHandler(nid):
    if(nid == "zi"):
        utils.sideWidgets["graph"].zoom(-1.0)
    elif(nid == "zo"):
        utils.sideWidgets["graph"].zoom(1.0)
    else:
        nid = int(nid)

utils.addSideWidget("graph", "[Path] Afficher / cacher le graphe.", "Shift+G", graphLinkHandler,
                    QSize(100, 500), Qt.BottomDockWidgetArea, loadHeader = True)

def updateGraph():
    # On recupere le map du graphe. S'il n'y en a pas, c'est que le graphe n'a
    # pas ete genere, donc on arrete le process.
    try:
        cmapxFile = open(graphMapName, "r")
        cmapx = "".join(cmapxFile.readlines())
        JS_load = """
            $("#drag").draggable();
            $("#zoomIn").button({icons: {primary: "ui-icon-zoomin"}});
            $("#zoomOut").button({icons: {primary: "ui-icon-zoomout"}});
        """
        utils.sideWidgets["graph"].update("""
        """, u"""
            <div id="zoom" style="position: absolute;
                left: 100px;
                top: 10px;
                z-index:1000;
                padding:10px;
                border-radius: 10px;
                border: 2px solid #8AC007;
                background-color:#FFF;">
                                        <button id="zoomIn" onclick="py.link('zo');" style="margin-right:10px;"></button>
                <button id="zoomOut" onclick="py.link('zi');" ></button>
            </div>
            <div id="drag">
                <img src="graph.png" usemap="#G" id="graph"
                                        style="cursor: move" />
                %s
            </div>
            """ %(utils.escapeToHtml(cmapx)), JS = JS_load)
    except IOError:
        pass

def graphFocusNode(noteId):
    JS_script = """
        $('html, body').animate({
            scrollTop: $("area[href='%d']").offset().top
        }, 500);
    """ % (noteId)
    utils.sideWidgets["graph"].exeJS(JS_script)

anki.hooks.addHook("profileLoaded", updateGraph)
