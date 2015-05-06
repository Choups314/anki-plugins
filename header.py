from aqt.reviewer import Reviewer
from anki.hooks import wrap
#from aqt.utils import showInfo

JS_scripts = [
    "jquery/jquery.js",
    "jquery/jquery-ui.js",
    "jquery/wheelzoom.js"
]

CSS_files = [
    "jquery/jquery-ui.css"
]

# Le code JavaScript suivant est execute des que tous les fichiers JS quand le
# contenu HTML est modifie (quand tous les fichiers JS ont ete charges)
update = """ """

##############################################################################
# On genere un script qui va charger chaque fichier javascript de facon
# synchrone (L'un apres l'autre)
##############################################################################

def genLoadRessources(JSupdate):
    if len(JS_scripts) == 0:
        return ""
    cssFiles = ""
    for f in CSS_files:
        cssFiles += """$("head").append( $("<link rel='stylesheet' type='text/css' href='%s'>")); \n""" % f
    script = """
        function callback%d() {
            // Every JS files have been loaded !
            // Now, load the CSS files (It requires jquery to be loaded !)
            %s
            %s
        }
    """ % (len(JS_scripts), cssFiles, JSupdate)
    for i in xrange(len(JS_scripts)):
        script += """
            function callback%d() {
                var script = document.createElement("script");
                script.type = "text/javascript";
                script.src = "%s";
                script.onreadystatechange = callback%d;
                script.onload = callback%d;
                document.body.appendChild(script);
            }
        """ % (i, JS_scripts[i], i+1, i+1)
    # L'appel a la premiere fonction
    script += """callback0();"""
    return script

def loadHeader(web, JSupdate=""):
    web.eval(genLoadRessources(JSupdate))
