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

# CREATE TABLE `PATH.nodes` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `noteId`noteIdINTEGER
# );

# CREATE TABLE `PATH.match` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `nodeId`nodeIdINTEGER,
#         `str`strTEXT,
#         `primary`primaryINTEGER DEFAULT 0
# );


#######################################################################
# Creation du graph
#######################################################################

# def nextStep(from, history):
#     next = mw.col.db.execute("""
#         SELECT

def makePath(chap):
    """ @chap : Start from a node that belongs to the current chapter. """
    global currentChap
    # On prend un noeud principal au hasard qui correspond au chapitre etudie
    startNode = -1
    try:
        if chap:
            chapNotes = "".join(str(n) + "," for n in chapters.getNotesOfChapter(currentChap))
            startNode = mw.col.db.execute("""
                SELECT nodeId FROM `PATH.match` AS M
                    JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                    WHERE `primary` = 1 AND noteId IN (%s)
                    ORDER BY RANDOM()
                """ % (chapNotes[:-1])).fetchone()[0]
        else:
            startNode = mw.col.db.execute("SELECT nodeId FROM `PATH.match` WHERE `primary` = 1 ORDER BY RANDOM()").fetchone()[0]
    except:
        # Aucun noeuds dans la bdd ?
        return
    # Enfin, on cree le graph
    graph = [startNode]


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
# On ajoute un textEdit dans l'edition d'une note, pour matcher la note avec un nom
#######################################################################

def setNote():
    rawString = utils.noteWInst["noteMatch"].text()
    strings = rawString.split(";")
    note = utils.currentNote
    # On commence par ajouter un neoud, s'il n'y en a pas deja un.
    if(mw.col.db.execute("""SELECT COUNT(id) FROM `PATH.nodes` WHERE noteId = %d"""
                         % (note.id)).fetchone()[0] == 0):
        mw.col.db.execute("""INSERT INTO `PATH.nodes` (noteId) VALUES (%d)"""
                          % (note.id))
    nodeId = mw.col.db.execute("SELECT id FROM `PATH.nodes` WHERE noteId = %d LIMIT 1" % (note.id)).fetchone()[0]
    # On reset tous les match de ce noeud
    mw.col.db.execute("DELETE FROM `PATH.match` WHERE nodeId=%d" % (nodeId))
    for s in strings:
        s = s.strip()
        if s == '': continue
        primary = 0
        if s[0] == '@':
            primary = 1
            s = s[1:]
        mw.col.db.execute("INSERT INTO `PATH.match` (nodeId, str, primary) VALUES (%d, '%s', %d)" % (nodeId, s, primary))

def initButton(b):
    b.setText("Set")

utils.addNoteWidget("noteMatch", QLineEdit)
utils.addNoteWidget("noteMatchAdd", QPushButton, "clicked()", setNote, initButton)

# On hook Editor.loadNote pour mettre a jour notre QLineEdit

def myLoadNote(self, _old):
    _old(self)
    names = ""
    for s in mw.col.db.execute("""
        SELECT str FROM `PATH.match` AS M
            JOIN `PATH.nodes` AS N ON M.nodeId = N.id
                                WHERE noteId=%d""" % (self.note.id)):
        names += s[0] + ";"
    # On n'oublie pas d'enlever le dernier point virgule
    utils.noteWInst["noteMatch"].setText(names[:-1])

Editor.loadNote = wrap(Editor.loadNote, myLoadNote, "loadNote")

#######################################################################
# On stocke les relations entre les differentes notes dans la bdd
#######################################################################

# CREATE TABLE `PATH.links` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `n1`n1INTEGER,
#         `n2`n2INTEGER
# );
# n1, n2 : Id des noeuds relies. (Les liens sont bidirectionnels).

# Les parametres de commandes envoyes a coqtop (sous forme d'une liste de
# chaines de caracteres
coqArgs = []

# On ajoute notre bouton (lors de l'affichage des cartes dans le reviewer) pour
# mettre a jour les liens de la carte en cours d'affichage.

def onCreateLinks():
    mw.progress.start(immediate=True)
    createLinksFor(utils.currentNote.id)
    mw.progress.finish()

def addCreateLinksButton(self, m):
    m.addSeparator()
    a = m.addAction("Rechercher les liens")
    #m.setShortcut(QKeySequence("Shift+L"))
    a.connect(a, SIGNAL("triggered()"), onCreateLinks)

addHook("Reviewer.contextMenuEvent", addCreateLinksButton)

# Les differents fichiers a charger (avec leur prefixe de librairie) sont
# stocker dans la bdd :

# CREATE TABLE `PATH.files` (
#         `id`idINTEGER PRIMARY KEY AUTOINCREMENT,
#         `file`fileTEXT,
#         `loadOrder`loadOrderINTEGER,
#         `enable`enableINTEGER
# );

# Notre instance de coqtop
coqInst = None

def coq():
    """ Load the coqtop process at the first call. """
    global coqInst
    if coqInst is None or not coqInst.alive():
        coqInst = coqpyth.initCoq(coqArgs)
        mw.progress.update(label="Load coq files ..")
        for f in mw.col.db.execute("SELECT file FROM `PATH.files`"):
            coqInst.interp("Require Import %s." % f[0])
    return coqInst

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
    c = coq()
    for matchStr in mw.col.db.execute("SELECT str FROM `PATH.match` WHERE nodeId=%d" % (nodeId)):
        mw.progress.update(label="Searh for " + matchStr[0])
        # Puis on analyse la version actuelle du code
        resp = c.interp("SearchAbout %s." % (matchStr[0]))[0].get()
        if resp[0]:
            # Si il n'y a pas eu d'erreurs, on analyse la reponse
            parse(nodeId, resp[1])

# On analyse la reponse de coqtop
def parse(nodeId, resp):
    mw.progress.update(label="Parse ...")
    lines = resp.split('\n')
    # On supprime deja la premiere ligne (Le Warning)
    lines = lines[1:]
    # Puis on ne prend que les noms des theoremes (en se basant sur
    # l'indentation et les deux-points qui seraprent le nom du type.
    names = []
    for l in lines:
        if len(l) >= 1 and l[0].strip() != '':
            names.append(l.split(':')[0])
    # On ne traite que les noms qui ont un match correspondant (donc  qui
    # appartiennent a un noeud.
    for n in names:
        nameNodeId = -1
        try:
            nameNodeId = mw.col.db.execute("""
                    SELECT nodeId FROM `PATH.match` WHERE str='%s'
                    """ % (n)).fetchone()[0]
        except:
            continue
        mw.col.db.execute("INSERT INTO `PATH.links` (n1, n2) VALUES (%d, %d)"
                          % (nodeId, nameNodeId))
