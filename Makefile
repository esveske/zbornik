
LATEXFLAGS := \
	-xelatex \
	-cd- \
	-latexoption=-shell-escape \
	-latexoption=-interaction=nonstopmode \

all: algpseudocodex y2020

algpseudocodex:
	mkdir -p ~/texmf/tex/latex/algpseudocodex
	wget https://mirrors.ctan.org/macros/latex/contrib/algpseudocodex/algpseudocodex.sty 
	mv algpseudocodex.sty ~/texmf/tex/latex/algpseudocodex/
	texhash ~/texmf

y2020:
	for i in $$PWD/2020/*/*/plots.gnu; do cd $$(dirname $$i); gnuplot plots.gnu || exit 1; done
	latexmk $(LATEXFLAGS) zb2020.tex
	mkdir -p output/
	zip output/output.zip zb2020.pdf 

clean:
	latexmk $(LATEXFLAGS) -C zb2020.tex
	rm -f *.log *.auxlock *.pdf
	rm -f */*/*/plot_*.pdf
	rm -rf output/