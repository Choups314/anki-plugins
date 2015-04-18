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

# CREATE TABLE `PATH.nodes` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `noteId`noteIdINTEGER
# );

# CREATE TABLE `PATH.match` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `nodeId`nodeIdINTEGER,
#         `str`strTEXT
# );

#######################################################################
# On ajoute un widget en haut, qui contiendra les questions (des liens)
#######################################################################

currentChap = ""
def linkHandler(link):
    if link == "questionAll":
        makePath(False)
    elif link == "questionChap":
        makePath(True)

utils.addSideWidget("path", "[Path] Afficher/cacher les liens.", "Shift+P", linkHandler,
                    QSize(1, 100), Qt.TopDockWidgetArea)

def showQuestion():
    global currentChap
    currentChap = chapters.getChapter(utils.currentNote.id)
    utils.sideWidgets["path"].update("", """
            <table width="100%%"><tr>
            <td align=center><button onclick="py.link('questionAll');">Question TOUT</button></td>
            <td align=center><button onclick="py.link('questionChap');">Question CHAPITRE (%s)</button></td>
            </tr></table>""" % utils.escapeToHtml(currentChap))

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
                                   WHERE noteId=%d""" % (utils.currentNote.id)):
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
        self.ui.form.content.setText(self.matchs[self.currIndex])
        self.ui.form.num.setText(str(self.currIndex + 1) + " / " + str(len(self.matchs)))

    def onTextChanged(self):
        self.matchs[self.currIndex] = self.ui.form.content.toPlainText()

    def reject(self):
        # On commence par ajouter un neoud, s'il n'y en a pas deja un.
        if(mw.col.db.execute("""SELECT COUNT(id) FROM `PATH.nodes` WHERE noteId = %d"""
                             % (self.nid)).fetchone()[0] == 0):
            mw.col.db.execute("""INSERT INTO `PATH.nodes` (noteId) VALUES (%d)"""
                              % (self.nid))
        nodeId = mw.col.db.execute("SELECT id FROM `PATH.nodes` WHERE noteId = %d LIMIT 1" % (self.note.id)).fetchone()[0]
        # On reset tous les match de ce noeud
        mw.col.db.execute("DELETE FROM `PATH.match` WHERE nodeId=%d" % (nodeId))
        for s in self.matchs:
            s = s.strip()
            if s == '': continue
            mw.col.db.execute("INSERT INTO `PATH.match` (nodeId, str) VALUES (%d, '%s')" % (nodeId, s))

def initButton(b):
    b.setText("Set matchs")

def setMatchs():
    utils.displayDialog("setMatch", addMatch_ui.Ui_Form, SetMatchModel,
            500, 500, "Add match", True, utils.currentNote)

utils.addNoteWidget("noteMatchAdd", QPushButton, "clicked()", setMatchs, initButton)


#######################################################################
# Les differentes actions affichees lors du review d'une carte
######################################################################

def setLink():
    createLinksFor(utils.currentNote.id)

# On ajoute notre bouton (lors de l'affichage des cartes dans le reviewer) pour
# definir les match

def addCreateLinksButton(self, m):
    m.addSeparator()
    a = m.addAction("Set matchs")
    a.setShortcut(QKeySequence("Shift+M"))
    a.connect(a, SIGNAL("triggered()"), setMatchs)

    a = m.addAction("Set link")
    a.setShortcut(QKeySequence("Shift+L"))
    a.connect(a, SIGNAL("triggered()"), setLink)

addHook("Reviewer.contextMenuEvent", addCreateLinksButton)


#######################################################################
# On stocke les relations entre les differentes notes dans la bdd
#######################################################################

# CREATE TABLE `PATH.links` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `matchId`matchIdINTEGER,
#         `noteId`noteIdINTEGER
# );

def createLinksFor(noteId):
    global coqArgs
    global coqInst
    """ Delete every links of this node, and recreate them. """
    # On commence par recuperer les infos sur la note
    nodeId = None
    try:
        nodeId = mw.col.db.execute("SELECT id FROM `PATH.nodes` WHERE noteId=%d" % (noteId)).fetchone()[0]
    except TypeError:
        # Si il n'y a aucun resultat, on quitte.
        return
    # On supprime les anciens liens ...
    mw.col.db.execute("DELETE FROM `PATH.links` WHERE n1 = %d OR n2 = %d" % (nodeId, nodeId))
    for matchStr in mw.col.db.execute("SELECT str FROM `PATH.match` WHERE nodeId=%d" % (nodeId)):
        mw.progress.update(label="Searh for " + matchStr[0])
        # Puis on analyse la version actuelle du code
        resp = c.interp("SearchAbout %s." % (matchStr[0]))[0].get()
        if resp[0]:
            # Si il n'y a pas eu d'erreurs, on analyse la reponse
            parse(nodeId, resp[1])

