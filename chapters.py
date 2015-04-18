from aqt import *
import aqt
from aqt.utils import showInfo
from aqt import mw
import addChapter_ui
from aqt.editor import Editor
from anki.hooks import wrap, addHook
from aqt.qt import *
from anki.utils import splitFields
import utils
import noteChanger

# CREATE TABLE `CHAP.chapters` (
#         `id`idINTEGER,
#         `chapitre`chapitreTEXT,
#         `noteType`noteTypeTEXT,
#         `toc`tocTEXT,
#         PRIMARY KEY(id)
# );

# CREATE TABLE `CHAP.toc` (
#         `id`idINTEGER,
#         `chapId`chapIdINTEGER,
#         `noteId`noteIdINTEGER,
#         `part`partINTEGER,
#         `position`positionINTEGER,
#         PRIMARY KEY(id)
# );

#####################################################################
# Le widget qui contient le sommaire
#####################################################################

tocItemCallback = None

# On affiche la reponse de la carte cliquee
def linkHandler(nid):
    if tocItemCallback is None:
        noteChanger.changeCard(int(nid), True)
    else:
        tocItemCallback(int(nid))

utils.addSideWidget("toc", "[Chap] Afficher/cacher le sommaire.", "Shift+T", linkHandler,
                    QSize(200, 100), Qt.RightDockWidgetArea)

#####################################################################
# On cree un sommaire (html) pour une carte donnee a partir de la bdd
#####################################################################

def makeTOCFromNoteId(noteId):
    try:
        chapId = mw.col.db.execute("SELECT chapId FROM `CHAP.toc` WHERE noteId=%d" % (noteId)).fetchone()[0]
        makeTOC(chapId, noteId)
    except: pass

def makeTOCFromChapName(chap):
    try:
        chapId = mw.col.db.execute("SELECT id FROM `CHAP.chapters` WHERE chapitre='%s'" % chap).fetchone()[0]
        makeTOC(chapId)
    except: pass

def makeTOC(chapId, focusNid = -1):
    # On recupere le modele du sommaire (les titres des differentes parties)
    (chapitre, noteType, partsRaw) = mw.col.db.execute("SELECT chapitre, noteType, toc FROM `CHAP.chapters` WHERE id=%d" % (chapId)).fetchone()
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
        for nid, mid, flds in mw.col.db.execute("SELECT id, mid, flds FROM notes WHERE id IN (SELECT noteId FROM `CHAP.toc` WHERE chapId=%d AND part=%d ORDER BY position)" % (chapId, i)):
            fields = splitFields(flds)
            span = "<span>"
            if(nid == focusNid):
                span = "<span id='currentCard'>"
            html += """<li>%s<a href='%s'>%s</a></span></li>""" % (span, nid, fields[notes[int(mid)]])
        html += "</ul></li>"
        i += 1
    html += "</ul>"
    utils.sideWidgets["toc"].update("""
                            border-width:2px;
                            border-style:solid;
                            margin:10px;""",
                                    "<h1><u><i>Sommaire</i> : %s</u></h1><br>%s" %
                                        (chapitre, html))

def showQuestion():
    global tocItemCallback
    tocItemCallback = None
    noteId = mw.reviewer.card.nid
    makeTOCFromNoteId(noteId)

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
    for id, chapter, noteType in mw.col.db.execute("SELECT id, chapitre,noteType FROM `CHAP.chapters`"):
        infos = noteType_parse(noteType, note.mid)
        if infos and note.fields[int(infos[0])] == chapter:
            chap = int(id)
    if chap == "":
        print("Cannot add this note !")
        return
    # Si on a deja une entree pour cette note, on la met a jour
    newEntry = True
    for id in mw.col.db.execute("SELECT id FROM `CHAP.toc` WHERE noteId=%d AND chapId=%d" % (note.id, chap)):
        newEntry = False
        if newPart != -1:
            mw.col.db.execute("UPDATE `CHAP.toc` SET part=%d WHERE noteId=%d AND chapId=%d" % (newPart, note.id, chap))
        else:
            mw.col.db.execute("UPDATE `CHAP.toc` SET position=%d WHERE noteId=%d AND chapId=%d" % (newPos, note.id, chap))
        break
    if newEntry:
        # Sinon, on cree une nouvelle entree
        if newPart != -1:
            mw.col.db.execute("INSERT INTO `CHAP.toc` (chapId, noteId, part, position) VALUES (%d, %d, %d, 1)" % (chap, note.id, newPart))
        else:
            mw.col.db.execute("INSERT INTO `CHAP.toc` (chapId, noteId, position, part) VALUES (%d, %d, %d, 1)" % (chap, note.id, newPos))


#####################################################################
# On ajoute le champ pour placer une carte dans une categorie
#####################################################################

def onValueChangedPart(i):
    editNote(utils.currentNote, i, -1)

def onValueChangedPosition(i):
    editNote(utils.currentNote, -1, i)

utils.addNoteWidget("partSpin", QSpinBox, "valueChanged(int)", onValueChangedPart)
utils.addNoteWidget("positionSpin", QSpinBox, "valueChanged(int)", onValueChangedPosition)

#####################################################################
# On hook Editor.loadNote pour mettre a jour les spin
#####################################################################

def myLoadNote(self, _old):
    _old(self)
    # Si la note est presente dans la table toc, alors on met a jour les spins
    contained = True
    for part, position in mw.col.db.execute("SELECT part, position FROM `CHAP.toc` WHERE noteId=%d" % (self.note.id)):
        utils.noteWInst["partSpin"].setValue(part)
        utils.noteWInst["positionSpin"].setValue(position)
        contained = False
        break
    if contained:
        utils.noteWInst["partSpin"].setValue(0)
        utils.noteWInst["positionSpin"].setValue(0)

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

#####################################################################
# Fonctions pour des plugins externes :
#   - getChapter(noteId) Retourne les infos du chapitre de la note
#   - getNotesOfChapter(chap) Retourne les ID des notes qui sont dans le chapitre
#   (sous forme d'une liste)
#####################################################################

def getChapter(noteId):
    note = mw.col.getNote(noteId)
    mid = note.mid
    # On parcourt toutes les notes geree
    for chapitre, notesType in mw.col.db.execute("SELECT chapitre, noteType FROM `CHAP.chapters`"):
        for noteType in notesType.split('\n'):
            infos = noteType_parse(noteType, mid)
            if infos and note.fields[int(infos[0])] == chapitre:
                return chapitre
    return ""

def getNotesOfChapter(chap):
    notes = []
    notesType = mw.col.db.execute("SELECT noteType FROM `CHAP.chapters` WHERE chapitre='%s' LIMIT 1" % (chap)).fetchone()[0]
    for noteType in notesType.split('\n'):
        infos = noteType.split('::')
        for id, flds in mw.col.db.execute("SELECT id, flds FROM notes WHERE mid=%d" % int(infos[0])):
            if chap == splitFields(flds)[int(infos[1])]:
                notes.append(id)
    return notes

# On ajoute la possibilite de definir une callback utilisateur lors d'un clique
# sur un item du sommaire
# Le comportement par defaut revient a chaque chargement de carte

def setTocCallback(callback = None):
    global tocItemCallback
    tocItemCallback = callback

def displayChapter(chap):
    makeTOCFromChapName(chap)

