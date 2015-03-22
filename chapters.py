from aqt import *
import aqt
import anki
from aqt.utils import showInfo
from aqt import mw
import addChapter_ui
from aqt.editor import Editor
from anki.hooks import wrap, addHook
from aqt.qt import *
from aqt.webview import AnkiWebView
from anki.utils import splitFields

#CREATE TABLE `chapters` (
#        `id`idINTEGER,
#        `chapitre`chapitreTEXT,
#        `noteType`noteTypeTEXT,
#        `toc`tocTEXT,
#        PRIMARY KEY(id)
#);

#####################################################################
# Le widget qui contient le sommaire
#####################################################################

class Toc():
    def __init__(self, mw):
        self.mww = mw
        self.dock = None
        self.web = None
        self.content = ""
        addHook("reviewCleanup", self.hide)
        addHook("deckCloosing", self.hide)
        self.show()

    def toggle(self):
        if self.shown:
            self.hide()
        else:
            self.show()

    def show(self):
        class TocWebView(AnkiWebView):
            def sizeHint(self):
                return QSize(200, 100)
        class DockableWithClose(QDockWidget):
            def closeEvent(self, event):
                self.emit(SIGNAL("closed"))
                QDockWidget.closeEvent(self, event)
        self.web = TocWebView()
        if self.content != "":
            self.web.setHtml(self.content)
        self.dock = DockableWithClose("", mw)
        self.dock.setObjectName("")
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.dock.setWidget(self.web)
        mw.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.shown = True

    def hide(self):
        mw.removeDockWidget(self.dock)
        self.shown = False

    def update(self, chapter, html):
        self.content = ("""<html><body><h1><u><i>Sommaire</i> : %s</u></h1><br>%s</body></html>""" % (chapter, html))
        self.web.setHtml(self.content)

_toc = Toc(mw)
def toggleToc(a):
    _toc.toggle()

toggleTOC = QAction("[Chap] Afficher/cacher le sommaire.", mw)
toggleTOC.setCheckable(True)
toggleTOC.setShortcut(QKeySequence("Shift+T"))
mw.form.menuTools.addAction(toggleTOC)
mw.connect(toggleTOC, SIGNAL("toggled(bool)"), toggleToc)

#####################################################################
# On cree un sommaire (html) pour une carte donnee a partir de la bdd
#####################################################################

import operator

def makeTOC(noteId):
    # On recupere l'ID du chapitre de la carte
    for chapId in mw.col.db.execute("SELECT chapId FROM toc WHERE noteId=%d" % (noteId)):
        # On recupere le modele du sommaire (les titres des differentes parties)
        for chapitre, noteType, partsRaw in mw.col.db.execute("SELECT chapitre, noteType, toc FROM chapters WHERE id=%d" % (chapId)):
            notes = {}
            for n in noteType.split('\n'):
                infos = n.split('::')
                notes[int(infos[0])] = int(infos[2])
            parts = partsRaw.split("\n")
            html = "<ul>"
            i = 1
            for p in parts:
                html += "<li><h2>%s</h2><ul>" % (p)
                # Enfin, on recupere toutes les notes qui sont dans cette partie
                for mid, flds in mw.col.db.execute("SELECT mid, flds FROM notes WHERE id IN (SELECT noteId FROM toc WHERE chapId=%d AND part=%d ORDER BY position)" % (chapId[0], i)):
                    fields = splitFields(flds)
                    html += "<li>" + fields[notes[int(mid)]] + "</li>"
                html += "</ul></li>"
                i += 1
            html += "</ul>"
            _toc.update(chapitre, html)
            break
        break

def showQuestion():
    noteId = mw.reviewer.card.nid
    makeTOC(noteId)

addHook("showQuestion", showQuestion)

#####################################################################
# On ajoute/met a jour une carte a un chapitre dans la bdd
#####################################################################
def noteType_parse(noteType, mid):
    for n in noteType.split('\n'):
        infos = n.split('::')
        if str(mid) == infos[0]:
            return (infos[1], infos[2])
    return False

def editNote(note, newPart, newPos):
    chap = ""
    # On commence par verifier que ce type de carte est bien pris en compte, et
    # que le chapitre correspond egalement
    for id, chapter, noteType in mw.col.db.execute("SELECT id, chapitre,noteType FROM chapters"):
        infos = noteType_parse(noteType, note.mid)
        if infos and note.fields[int(infos[0])] == chapter:
            chap = int(id)
    if chap == "":
        showInfo("Cannot add this note !")
        return
    # Si on a deja une entree pour cette note, on la met a jour
    newEntry = True
    for id in mw.col.db.execute("SELECT id FROM toc WHERE noteId=%d AND chapId=%d" % (note.id, chap)):
        newEntry = False
        if newPart != -1:
            mw.col.db.execute("UPDATE toc SET part=%d WHERE noteId=%d AND chapId=%d" % (newPart, note.id, chap))
        else:
            mw.col.db.execute("UPDATE toc SET position=%d WHERE noteId=%d AND chapId=%d" % (newPos, note.id, chap))
        break
    if newEntry:
        # Sinon, on cree une nouvelle entree
        if newPart != -1:
            mw.col.db.execute("INSERT INTO toc (chapId, noteId, part, position) VALUES (%d, %d, %d, 1)" % (chap, note.id, newPart))
        else:
            mw.col.db.execute("INSERT INTO toc (chapId, noteId, position, part) VALUES (%d, %d, %d, 1)" % (chap, note.id, newPos))


#####################################################################
# On ajoute le champ pour placer une carte dans une categorie
#####################################################################

partSpin = None
positionSpin = None
current = None

def onValueChangedPart(i):
    global current
    editNote(current.note, i, -1)

def onValueChangedPosition(i):
    global current
    editNote(current.note, -1, i)

def addTextEdit(self):
    global current
    global partSpin
    global positionSpin
    current = self
    partSpin = QSpinBox()
    partSpin.connect(partSpin, SIGNAL("valueChanged(int)"), onValueChangedPart)
    positionSpin = QSpinBox()
    positionSpin.connect(positionSpin, SIGNAL("valueChanged(int)"), onValueChangedPosition)
    self.iconsBox.addWidget(partSpin)
    self.iconsBox.addWidget(positionSpin)

anki.hooks.addHook("setupEditorButtons", addTextEdit)

#####################################################################
# On hook Editor.loadNote pour mettre a jour les spin
#####################################################################

def myLoadNote(self, _old):
    global partSpin
    global positionSpin
    _old(self)
    # Si la note est presente dans la table toc, alors on met a jour les spins
    contained = True
    for part, position in mw.col.db.execute("SELECT part, position FROM toc WHERE noteId=%d" % (self.note.id)):
        partSpin.setValue(part)
        positionSpin.setValue(position)
        contained = False
        break
    if contained:
        partSpin.setValue(0)
        positionSpin.setValue(0)

Editor.loadNote = wrap(Editor.loadNote, myLoadNote, "loadNote")

#####################################################################
# Fenetre pour ajouter un chapitre
#####################################################################

class AddChapter(QDialog):
    def __init__(self, mww):
        QDialog.__init__(self, None, Qt.Window)
        self.__init__mww = mww
        self.form = addChapter_ui.Ui_Form()
        self.form.setupUi(self)
        self.show()
        self.form.valid.connect(self.form.valid, SIGNAL("clicked()"), self.onAdd)

    def onAdd(self):
        partsRaw = self.form.parts.toPlainText()
        notesRaw = self.form.notes.toPlainText()
        chapter = self.form.chapter.text()
        mw.col.db.execute("INSERT INTO `chapters` (`toc`, `noteType`, `chapitre`) VALUES ('%s', '%s', '%s')" % (partsRaw, notesRaw, chapter))
        self.form.parts.clear()
        self.form.notes.clear()
        self.form.chapter.setText("")
    def reject(self):
        aqt.dialogs.close("AddChapter")
        QDialog.reject(self)

#####################################################################
# Menu pour editer le sommaire
#####################################################################

def exeAddChapter():
    aqt.dialogs._dialogs["AddChapter"] = [AddChapter, None]
    aqt.dialogs.open("AddChapter", mw)

addTOC = QAction("[Chaps] Ajouter un chapitre", mw)
mw.connect(addTOC, SIGNAL("triggered()"), exeAddChapter)
mw.form.menuTools.addAction(addTOC)

