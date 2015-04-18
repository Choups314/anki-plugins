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

# Le mid (type de carte)  des cartes a prendre en compte
midFilter = [1421169816293]
# Pour chaque type de carte, l'index du champs qui indique le chapitre
chapterField = {1421169816293 : 1}

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
# Un widget qui permet de selectionner un match
#######################################################################

class MatchSelectorModel:
    def __init__(self, ui, noteId):
        self.ui = ui
        self.noteId = noteId[0]
        # Avec cet appel, on est sur que le noeud existe bien
        self.nodeId = getNodeId(self.noteId)
        self.ui.form.matchsList.connect(self.ui.form.matchsList, SIGNAL("doubleClicked(QModelIndex)"), self.onDoubleClicked)
        self.ui.form.edit.connect(self.ui.form.edit, SIGNAL("clicked()"), self.onEdit)
        self.updateList()

    def onEdit(self):
        setMatchs(mw.col.getNote(self.noteId))

    def onDoubleClicked(self, modelIndex):
        def addLinkIfNotExists(matchId, noteId):
            if (mw.col.db.execute("""SELECT COUNT(id) FROM `PATH.links`
                        WHERE matchId=%d AND noteId=%d"""
                        % (matchId, noteId)).fetchone()[0] == 0) :
                mw.col.db.execute("""
                    INSERT INTO `PATH.links` (matchId, noteId)
                    VALUES (%d, %d)""" % (matchId, noteId))

        row = modelIndex.row()
        # On ajoute le lien (Si il n'est pas deja present) et on reaffiche les
        # liens. Enfin on ferme cette fenettre
        if row == 0: # Si c'est le "Default"
            # On recuperre l'ID du match Default
            defaultMatchId = mw.col.db.execute("""
                    SELECT M.id FROM `PATH.match` AS M
                        WHERE nodeId=%d LIMIT 1""" % self.nodeId).fetchone()[0]
            addLinkIfNotExists(defaultMatchId, utils.currentNote.id)
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
    utils.displayDialog("matchSelector", matchSelector_ui.Ui_Form, MatchSelectorModel,
                        500, 500, "Match selector", False, noteId)

def showQuestion():
    note = utils.currentNote
    # On verifie que l'on gere cette carte ...
    if note.mid in midFilter:
        chap = note.fields[chapterField[note.mid]]
        # A priori, le sommaire n'est pas encore afifche
        chapters.displayChapter(chap)
        chapters.setTocCallback(onTocClicked)
        # On affiche les liens
        displayLinks(note.id)

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

def linkHandler(link):
    showInfo(link)

utils.addSideWidget("links", "[PATH] Afficher / cacher les liens.", "Shift+L", linkHandler,
        QSize(200, 100), Qt.LeftDockWidgetArea, loadHeader=True)

def displayLinks(noteId):
    # On ajoute chaque lien dans un accordeon Jquery
    html = """<div id="accordion">\n"""
    # On les recupere d'abord dans la bdd
    for s, nid in mw.col.db.execute("""SELECT M.str, N.noteId FROM `PATH.links` AS L
        JOIN `PATH.match` AS M ON M.id = L.matchId
        JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                                    WHERE L.noteId = %d""" % (noteId)):
        html += "<h3>" + chapters.getLabel(nid) + "</h3>\n"
        # Traitement special pour le match "Default"
        if s == "":
            html += "<div></div>"
        else:
            html += "<div><p>" + s + "</p></div>\n"
    html += "</div>\n"
    utils.sideWidgets["links"].update("", html)
