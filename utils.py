from aqt.qt import *
import anki
from aqt.utils import showInfo, getBase
from anki.hooks import wrap, addHook
from aqt.webview import AnkiWebView
from aqt import mw
from aqt.editor import Editor
import aqt
import header

###########################################################################
# Ajout d'un widget dans la barre d'outils d'une note (lors de son edition)
###########################################################################

# Tous les widgets a afficher lors de l'edition d'une note
noteWidgets = []
# Et leurs instances
noteWInst = {}

def addNoteWidget(id, Class, signal = "", callback = None, init = None):
    """ Add an instance of the class @Class (and connect its SIGNAL @signal to
    the @callback SLOT) in the icon box of the current note edition. """
    global noteWidgets
    noteWidgets.append((Class, signal, callback, id, init))

# La note en cours d'edition ou en cours d'affichage
currentNote = None
# La carte en cours d'affichage (que pour le reviewer
currentCard = None

def setupWidgets(self):
    global currentNote
    global noteWidgets
    global noteWInst
    for w in noteWidgets:
        instance = w[0]()
        if(w[1] != ""):
            instance.connect(instance, SIGNAL(w[1]), w[2])
        if(w[4] != None):
            w[4](instance)
        self.iconsBox.addWidget(instance)
        noteWInst[w[3]] = instance

anki.hooks.addHook("setupEditorButtons", setupWidgets)

def updateCurrentNoteReviewer():
    global currentNote
    global currentCard
    currentNote = mw.reviewer.card.note()
    currentCard = mw.reviewer.card

addHook("showQuestion", updateCurrentNoteReviewer)
addHook("showAnswer", updateCurrentNoteReviewer)


def updateCurrentNoteEditor(self, _old):
    global currentNote
    currentNote = self.note
    _old(self)

Editor.loadNote = wrap(Editor.loadNote, updateCurrentNoteEditor, "loadNoteUtils")


###########################################################################
# Ajout d'un widget (avec une webview) dockable dans la fenetre globale
# On ajoute aussi une entree dans le menu "Outils" (avec un raccourci)
###########################################################################

class SideWidget():

    def __init__(self, linkHandler, sizeHint, dockArea, hasHeader, autoToggle):
        self.linkHandler = linkHandler
        self.sizeHint = sizeHint
        self.dockArea = dockArea
        self.hasHeader = hasHeader
        self.dock = None
        self.web = None
        self.content = ""
        addHook("reviewCleanup", self.hide)
        addHook("deckCloosing", self.hide)
        self.shown = False
        if autoToggle:
            addHook("showQuestion", self.checkAndShow)
        self.JS = ""

    def checkAndShow(self):
        if not self.shown:
            self.show()

    def toggle(self, a):
        if self.shown: self.hide()
        else: self.show()

    def show(self):
        class Webview(AnkiWebView):

            def __init__(self, sizeHint):
                super(Webview, self).__init__()
                self.s = sizeHint

            def sizeHint(self):
                return self.s

        class DockableWithClose(QDockWidget):

            def closeEvent(self, event):
                self.emit(SIGNAL("closed"))
                QDockWidget.closeEvent(self, event)

        self.web = Webview(self.sizeHint)
        self.web.setLinkHandler(self.linkHandler)
        if self.content != "":
            if self.hasHeader:
                self.web.stdHtml(self.content, head=getBase(mw.col))
            else:
                self.web.stdHtml(self.content)
        self.dock = DockableWithClose("", mw)
        self.dock.setObjectName("")
        #self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.dock.setWidget(self.web)
        mw.addDockWidget(self.dockArea, self.dock)
        self.shown = True
        if self.hasHeader:
            header.loadHeader(self.web)
        if self.JS != "":
            self.web.eval(self.JS)

    def hide(self):
        if self.shown:
            mw.removeDockWidget(self.dock)
            self.shown = False

    def update(self, style, html, JS=""):
        self.content = ("""<html><head>
                        <style type="text/css"> #currentCard {
                            %s
                        </style></head><body>%s</body></html>"""
                            % (style, html))
        self.JS = JS
        if not self.web is None:
            if self.hasHeader:
                self.web.stdHtml(self.content, head=getBase(mw.col))
                header.loadHeader(self.web)
            else:
                self.web.stdHtml(self.content)
            if self.JS != "":
                self.web.eval(self.JS)


# Tous les SideWidget affiches
sideWidgets = {}

def addSideWidget(id, menuLabel, shortcut, linkHandler,
                  sizeHint = QSize(100, 100), dockArea = Qt.RightDockWidgetArea,
                  defaultHtml = "", defaultStyle="", loadHeader=False, autoToggle=True):
    global sideWidgets
    instance = SideWidget(linkHandler, sizeHint, dockArea, loadHeader, autoToggle)
    menuAction = QAction(menuLabel, mw)
    menuAction.setCheckable(True)
    menuAction.setShortcut(QKeySequence(shortcut))
    mw.form.menuTools.addAction(menuAction)
    mw.connect(menuAction, SIGNAL("toggled(bool)"), instance.toggle)
    sideWidgets[id] = instance
    if defaultHtml != '':
        instance.update(defaultStyle, defaultHtml)

###########################################################################
# Misc fonctions
###########################################################################

html_escape_table = {
    233 : "&eacute"
}

def escapeToHtml(text):
    return "".join(html_escape_table.get(ord(c), c) for c in text)

###########################################################################
# Affichage d'une boite de dialogue
###########################################################################

class DialogWidget(QDialog):

    def __init__(self, id, UiClass, ModelClass, minHeight, minWidth, winTitle, processReject, args):
        QDialog.__init__(self, None, Qt.Window)
        self.id = id
        self.processReject = processReject
        self.form = UiClass()
        self.form.setupUi(self)
        if minHeight != -1: self.setMinimumHeight(minHeight)
        if minWidth != -1: self.setMinimumWidth(minWidth)
        self.setWindowTitle(_(winTitle))
        self.model = ModelClass(self, args)
        self.show()

    def reject(self):
        if self.processReject:
            self.model.reject()
        aqt.dialogs.close(self.id)
        QDialog.reject(self)

def displayDialog(id, UiClass, ModelClass, minHeight=-1, minWidth=-1, winTitle="", processReject=False, *args):
    # On n'ouvre qu'une seule instance a la fois
    if not id in aqt.dialogs._dialogs.keys():
        aqt.dialogs._dialogs[id] = [DialogWidget, None]
    aqt.dialogs.open(id, id, UiClass, ModelClass, minHeight, minWidth, winTitle, processReject, args)

###########################################################################
# Un widget qui affiche un contenu latex (il genere l'image si besoin)
###########################################################################

class LatexPreview(QPixmap):

        def __init__(self, container):
            QPixmap.__init__(self, container)

        def dispLatex(self, latex):
            showInfo(latex)
