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
        self.ui.form.matchsList.connect(self.ui.form.matchsList, SIGNAL("doubleClicked(QModelIndex)"), self.onDoubleClicked)
        self.ui.form.edit.connect(self.ui.form.edit, SIGNAL("clicked()"), self.onEdit)
        self.updateList()

    def onEdit(self):
        setMatchs(mw.col.getNote(self.noteId))

    def onDoubleClicked(self, modelIndex):
        matchId = self.matchIds[modelIndex.row()]
        # On ajoute le lien (Si il n'est pas deja present) et on ferme la fenetre
        if (mw.col.db.execute("""SELECT COUNT(id) FROM `PATH.links`
                             WHERE matchId=%d AND noteId=%d""" % (matchId, self.noteId)).fetchone()[0] == 0) :
            mw.col.db.execute("""
                INSERT INTO `PATH.links` (matchId, noteId)
                VALUES (%d, %d)""" % (matchId, self.noteId))
        self.ui.close()

    def updateList(self):
        self.matchs = []
        self.matchIds = {}
        self.ui.form.matchsList.clear()
        # On recupere la liste des matchs et on les affiche
        row = 0
        for matchId, s in mw.col.db.execute("""
            SELECT M.id, str FROM `PATH.match` AS M
            JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                                    WHERE noteId=%d""" % (self.noteId)):
            self.matchs.append(s)
            self.matchIds[row] = matchId
            row += 1
            self.ui.form.matchsList.addItem(s)

#######################################################################
# On ajoute un widget en haut, qui contiendra les questions (des liens)
#######################################################################

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
        pass
