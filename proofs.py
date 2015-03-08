import re
from anki.latex import _imgLink
from anki.hooks import wrap
from aqt.toolbar import Toolbar
from aqt.reviewer import Reviewer
from anki.media import MediaManager
from anki.latex import mungeQA as ankiMungeQA
import types
import aqt
from aqt.utils import showInfo
from aqt import mw
import anki

#######################################
### Variables et configuration globales
#######################################

# Le mid (type de carte) des cartes en prendre en compte
midFilter = []


### On modifie le HTML affiche pour les cartes filtrees
htmlUpdated = False
def myInitWeb(self, _old) :
	global htmlUpdated
	if not htmlUpdated:
		self._revHtml = """
<img src="qrc:/icons/rating.png" id=star class=marked>
<div id=qa></div>
<div><button id="next" onclick="next();">Suivant</button></div>
<script>

var currentChunk = -2;
var numChunks = 0;

var ankiPlatform = "desktop";
var typeans;

function next(){
	currentChunk++;
	$("#c" + currentChunk).show();
	$("#c" + currentChunk)[0].scrollIntoView();
	$("#next").html("OK");
	$("#next").html("Suivant (" + (currentChunk+1)  + " / " + numChunks + ")");
	if(currentChunk == numChunks - 1) {
		$("#next").hide();
	}
}

function _updateQA (q, answerMode, klass) {
	if(answerMode && q.indexOf("##>>") != -1 && q.indexOf("<<##") != -1) {
		var start = q.indexOf("##>>");
		var end = q.indexOf("<<##");
		var newHtml = q.substring(0, start);
		var chunks = q.substring(start + 4, end).split("###");
		var i = 0;
		newHtml += "<div id='proof'>";
		for (var c in chunks) {
			newHtml += "<div style='display:none;' class='proofNode' id='c" + i + "'>" + chunks[c] + "</div>";
			i++;
		}
		newHtml += "</div>";
		numChunks = i;
		newHtml += q.substring(end + 4);
		$("#qa").html(newHtml);
		$("#next").show();
		next();
	} else {
		$("#qa").html(q);
		$("#next").hide();
	}
	typeans = document.getElementById("typeans");
	if (typeans) {
		typeans.focus();
	}
	if (answerMode) {
		var e = $("#answer");
		if (e[0]) { e[0].scrollIntoView(); }
	} else {
		window.scrollTo(0, 0);
	}
	if (klass) {
	document.body.className = klass;
	}
	// don't allow drags of images, which cause them to be deleted
	$("img").attr("draggable", false);
};

function _toggleStar (show) {
    if (show) {
        $(".marked").show();
    } else {
        $(".marked").hide();
    }
}

function _getTypedText () {
    if (typeans) {
        py.link("typeans:"+typeans.value);
    }
};
function _typeAnsPress() {
    if (window.event.keyCode === 13) {
        py.link("ansHack");
    }
}
</script>
"""
		htmlUpdated = True
	return _old(self)

Reviewer._initWeb = wrap(Reviewer._initWeb, myInitWeb, "initWeb")

##########
def mungeQA(html, type, fields, model, data, col):
	start = html.find("#-#")
	end = html.find("#$#")
	if start!=-1 and end != -1:
		chunks = html[start+3 : end].split("###")
		sStart = html[:start]
		sEnd = html[end+3:]
		html = sStart + " ##>>"
		for i in xrange(len(chunks)):
			if i == 0:
				html += "[latex]" + chunks[i] + "[/latex]"
			else:
				html += "### [latex]" + chunks[i] + "[/latex]"
		html += "<<## " + sEnd
	return ankiMungeQA(html, type, fields, model, data, col)

# Change the order of the hooks (make ours first)
#anki.hooks.remHook("mungeQA", ankiMungeQA)
anki.hooks.addHook("mungeQA", mungeQA)
#anki.hooks.addHook("mungeQA", ankiMungeQA)

def showQuestion():
	pass

anki.hooks.addHook("showQuestion", showQuestion)
