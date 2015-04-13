from aqt.qt import *
import anki
from aqt.utils import showInfo

###########################################################################
# Ajout d'un widget dans la barre d'outils d'une note (lors de son edition)
###########################################################################

# Tous les widgets a afficher lors de l'edition d'une note
noteWidgets = []
# Et leurs instances
noteWInst = {}

def addNoteWidget(id, Class, signal, callback):
    """ Add an instance of the class @Class (and connect its SIGNAL @signal to
    the @callback SLOT) in the icon box of the current note edition. """
    global noteWidgets
    noteWidgets.append((Class, signal, callback, id))

# La note en cours d'edition
currentNote = None

def setupWidgets(self):
    global currentNote
    global noteWidgets
    global noteWInst
    currentNote = self
    for w in noteWidgets:
        instance = w[0]()
        instance.connect(instance, SIGNAL(w[1]), w[2])
        self.iconsBox.addWidget(instance)
        noteWInst[w[3]] = instance

anki.hooks.addHook("setupEditorButtons", setupWidgets)
