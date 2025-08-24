
LATEXFLAGS := \
	-xelatex \
	-cd- \
	-latexoption=-shell-escape \
	-latexoption=-interaction=nonstopmode \

all: y2020 # algpseudocodex

# This doesn't work (redownloads every time) files don't exist
algpseudocodex: 
	mkdir -p ~/texmf/tex/latex/algpseudocodex
	wget https://mirrors.ctan.org/macros/latex/contrib/algpseudocodex/algpseudocodex.sty 
	mv algpseudocodex.sty ~/texmf/tex/latex/algpseudocodex/
	texhash ~/texmf

refs2020: 2020/*/*/refs.bib
	echo "\033[0;31m REFS\033[0m"
	cat 2020/*/*/refs.bib > 2020/refs.bib
pandoc:
	unzip -qq -d docx templates/rad.docx
	mv docx/word/media .
	pandoc templates/rad.docx --lua-filter=./filter.lua -o izDocxa.tex
	cp templates/rad.tex .
	tectonic rad.tex
	rm rad.tex
	rm -rf docx/ media/

y2020: refs2020
	echo "\033[0;31m Y2020\033[0m"
	for i in $$PWD/2020/*/*/plots.gnu; do cd $$(dirname $$i); gnuplot plots.gnu || exit 1; done
	latexmk $(LATEXFLAGS) zb2020.tex
	mkdir -p output/
	zip output/output.zip zb2020.pdf 

clean:
	latexmk $(LATEXFLAGS) -C zb2020.tex
	rm -f *.log *.auxlock *.pdf
	rm -f */*/*/plot_*.pdf
	rm -rf output/
	rm -rf */refs.bib
	rm izDocxa.tex
	rm rad.tex
