from anki.hooks import wrap
from aqt.toolbar import Toolbar
from aqt import DialogManager
from aqt.qt import *
import types
import aqt
from aqt.utils import showInfo
import todo_ui
from aqt.webview import AnkiWebView
from aqt import mw
from anki.utils import splitFields
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt
import anki
from anki.collection import _Collection
from aqt.utils import tooltip, getBase
from anki.utils import json
import utils

####################################################
# Variables de configuration et variables globales
####################################################

# Le mid (type de carte)  des cartes a prendre en compte dans le TODO
midFilter = [1419157173874, 1421781450069, 1419152687852]
# Pour chaque type de carte, l'index du champs qui indique le chapitre
chapterField = {
    1419157173874: 4,
    1421781450069: 5,
    1419152687852: 2
}

# Dictionnaire <chapitre, [liste : id des cartes du chapitre]>
chapters = {}
# Un dictionnaire qui indique a quel chapitre appartient chaque note
# <NoteId, Chapitre>
notes = {}

#######################################################
# La fenetre de dialogue qui indique les TODO actuels
#######################################################


class TodoModel:

    _cardHTML = """
<div id=qa></div>
<script>
var ankiPlatform = "desktop";
var typeans;
function _updateQA (q) {
    $("#qa").html(q);
    $("img").attr("draggable", false);
};
</script>
<button	onclick="py.link('%s');">FAIT</button>
"""

    def showCards(self):
        global chapters
        for chap in chapters:
            self.cards[chap] = AnkiWebView()
            self.cards[chap].setLinkHandler(self.linkHandler)
            base = getBase(mw.col)
            self.cards[chap].stdHtml(self._cardHTML % chap, head=base)
            self.nextTodo(chap)
            self.ui.form.chapters.addItem(self.cards[chap], chap)
            self.cards[chap].show()


    def __init__(self, ui, *args):
        self.ui = ui

        # L'id des notes qui sont affichees actuelement (une par chapitre)
        self.currentNotes = {}

        # Affichage des cartes. Ca peut prendre du temps, car on peut avoir a
        # regenerer certaines images latex.
        mw.progress.start(immediate=True,label="Generation des cartes")
        self.cards = {}
        self.showCards()
        mw.progress.finish()

    def nextTodo(self, chap):
        # On recupere l'id de la prochaine carte
        (cardId, noteId) = getNextTodo(chap)
        if cardId == None:
            return
        self.currentNotes[chap] = noteId
        card = mw.col.getCard(cardId[0])
        # Affiche la reponse de la carte
        self.cards[chap].eval("_updateQA(%s, true);" % (json.dumps(card.a())))

    def linkHandler(self, chap):
        markDone(self.currentNotes[chap])
        self.nextTodo(chap)

##################################################
# Ajoute le bouton "TODO" sur la page principale
##################################################


def todoLinkHandler(self):
    utils.displayDialog("Todo", todo_ui.Ui_Dialog, TodoModel, 500, 500)

def myLinkHandler(self, link):
    if link == "todo":
        todoLinkHandler(self)
    self._linkHandlerOld(link)


def myCenterLinks(self, _old):
    linksHTML = _old(self)
    linksHTML += self._linkHTML([
        ["todo", _("TODO"), _("Shortcut key: %s") % "T"]
    ])
    self.myLinkHandler = types.MethodType(myLinkHandler, self)
    self.web.setLinkHandler(self.myLinkHandler)
    return linksHTML

Toolbar._centerLinks = wrap(Toolbar._centerLinks, myCenterLinks, "centerLinks")
Toolbar._linkHandlerOld = Toolbar._linkHandler
Toolbar._linkHandler = wrap(Toolbar._linkHandler, myLinkHandler, "linkHandler")

####################################################################
# Ajoute un bouton dans le menu qui permet de creer la table "todo"
####################################################################


def exeExtendDB():
    mw.col.db.execute(
        "CREATE TABLE `todo` (`cardId` INTEGER, `chapitre`TEXT, `logicOrder` INTEGER, `done`INTEGER)")
extendDB = QAction("TODO : construire la BDD", mw)
mw.connect(extendDB, SIGNAL("triggered()"), exeExtendDB)
mw.form.menuTools.addAction(extendDB)

##########################################################################
# Met a jour les dico "chapters" et "notes" a partir de la bdd actuelle
# Met aussi a jour la bdd (pour toutes les notes trouvee qui n'y sont pas encore)
##########################################################################


def updateChapters():
    global chapters
    global notes
    for id, mid, flds in mw.col.db.execute("SELECT id,mid,flds FROM notes"):
        if mid in midFilter:
            fields = splitFields(flds)
            chapter = fields[chapterField[mid]]
            if not (chapter in chapters):
                chapters[chapter] = []
            chapters[chapter].append(id)
            notes[id] = chapter
            # Si cette note n'est pas dans la table "todo", on l'ajoute
            count = 0
            for cardId in mw.col.db.execute("SELECT cardId FROM todo WHERE `cardId`=%d" % id):
                count += 1
            if count == 0:
                mw.col.db.execute(
                    "INSERT INTO `todo`(`cardId`,`chapitre`,`logicOrder`,`done`) VALUES (%d,'%s',0,0)" %
                    (id, chapter))
    tooltip("TODO : database loaded !", period=1000)

updateCardsAction = QAction("TODO : actualiser", mw)
mw.connect(updateCardsAction, SIGNAL("triggered()"), updateChapters)
mw.form.menuTools.addAction(updateCardsAction)

################################################################
# Permet de determiner le prochain "logicOrder" d'un chapitre
################################################################


def newOrderLogic(chap, id):
    global chapters
    logicOrders = []
    for cardId, logicOrder in mw.col.db.execute("SELECT cardId,logicOrder FROM todo WHERE chapitre='%s'" % chap):
        if cardId == id:
            continue
        logicOrders.append(logicOrder)
    if len(logicOrders) == 0:
        return 0
    return max(logicOrders) + 1

#############################################################
# Retourne le prochain todo a afficher pour un chaptire
# (Retourne l'id de la carte a afficher et l'id de la note)
#############################################################


def getNextTodo(chap):
    ids = {}
    for noteId, logicOrder in mw.col.db.execute("SELECT cardId, logicOrder FROM todo WHERE chapitre='%s' AND done=0" % chap):
        ids[logicOrder] = noteId
    if len(ids.keys()) == 0:
        return (None, None)
    noteId = ids[min(ids.keys())]
    # Retourne la premiere carte de cette note
    cardId = 0
    for id in mw.col.db.execute("SELECT id FROM cards WHERE nid='%d'" % noteId):
        cardId = id
        break
    return (cardId, noteId)

##########################################################################
# Ajoute un bouton dans l'editeur de carte qui permet d'ajouter un "logicOrder"
# a la carte en cours d'edition.
##########################################################################


def addLogicOrder(self):
    global notes
    if self.note.id in notes:
        id = self.note.id
        chap = notes[id]
        order = newOrderLogic(chap, id)
        mw.col.db.execute(
            "UPDATE todo SET `logicOrder`=%d WHERE `cardId`=%d" %
            (order, id))
        tooltip("Add logic order %d" % order, period=1000)


def addAddLogicOrderButton(self):
    self.addLogicOrder = types.MethodType(addLogicOrder, self)
    self._addButton("Add logic order", self.addLogicOrder)

anki.hooks.addHook("setupEditorButtons", addAddLogicOrderButton)

##########################################################################
# On wrap la fonction qui ajoute une note dans la base de donnee
# (On verifie si elle concerne le todo, et on met a jour la table "todo" si besoin
##########################################################################


def myAddNote(self, note):
    global chapters
    global midFilter
    mid = int(note.mid)
    if mid in midFilter:
        fields = note.fields
        id = note.id
        chapter = fields[chapterField[mid]]
        if not (chapter in chapters):
            chapters[chapter] = []
        chapters[chapter].append(id)
        notes[id] = chapter
        # On calcul le prochain logicOrder et on l'ajoute dans la bdd "todo"
        logicOrder = newOrderLogic(chapter, id)
        mw.col.db.execute(
            "INSERT INTO `todo`(`cardId`,`chapitre`,`logicOrder`,`done`) VALUES (%d,'%s',%d,0)" %
            (id, chapter, logicOrder))
        tooltip("Add card with logic order %d" % logicOrder, period=1000)
    return len(self.findTemplates(note))

_Collection.addNote = wrap(_Collection.addNote, myAddNote)

##########################################################################
# Un hook qui permet de savoir quand la bdd est chargee (Pour initialiser les variables
# Globales "chapters" et "notes"
##########################################################################


def startTodo():
    updateChapters()

anki.hooks.addHook("profileLoaded", startTodo)

##########################################################################
# Une fonction qui permet de supprimer tous les doublons (deux cartes qui ont le meme
# noteIde et le meme 'ord'
##########################################################################


def removeDuplicates():
    num = 0
    for noteId in mw.col.db.execute("SELECT id FROM notes"):
        i = 0
        while True:
            j = 0
            for cardId in mw.col.db.execute("SELECT id FROM cards WHERE `nid`=%d AND `ord`=%d" % (noteId[0], i)):
                if j >= 1:
                    mw.col.db.execute(
                        "DELETE FROM cards WHERE `id`=%d" %
                        cardId)
                    num += 1
                j += 1
            if j <= 1:
                break
            i += 1
    showInfo("%d doublons supprimes !" % num)
    return None

removeDuplicatesAction = QAction("TODO : Supprimer les doublons", mw)
mw.connect(removeDuplicatesAction, SIGNAL("triggered()"), removeDuplicates)
mw.form.menuTools.addAction(removeDuplicatesAction)

##########################################################################
# Une fonction qui permet de supprimer tous les doublons dans la table 'todo'
##########################################################################


def removeTODODuplicates():
    for cardId, chapitre, logicOrder, done in mw.col.db.execute("SELECT cardId, chapitre, logicOrder, done FROM todo"):
        # We first delete every records, and then we add a single one
        mw.col.db.execute("DELETE FROM todo WHERE `cardId`=%d" % cardId)
        #mw.col.db.execute("INSERT INTO `todo`(`cardId`,`chapitre`,`logicOrder`,`done`) VALUES (%d,'%s',%d,%d)" % (cardId, chapitre, logicOrder, done))
    return None

removeTODODuplicatesAction = QAction("TODO : Supprimer les doublons TODO", mw)
mw.connect(
    removeTODODuplicatesAction,
    SIGNAL("triggered()"),
    removeTODODuplicates)
mw.form.menuTools.addAction(removeTODODuplicatesAction)

####################################################
# Marque un todo comme fait (done = 1 dans la bdd)
####################################################


def markDone(noteId):
    mw.col.db.execute("UPDATE todo SET `done`=1 WHERE `cardId`=%d" % noteId)
