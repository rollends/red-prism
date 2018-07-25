DOCUMENTS = report.pdf slide_deck.pdf
PDFLATEX = pdflatex
BIBTEX = bibtex

all: $(DOCUMENTS)
	

clean:
	rm -rf $(DOCUMENTS) *.aux *.log *.bbl *.blg *.nav *.out *.snm *.toc

report.pdf: root.tex root.bib figures/*.eps
	$(PDFLATEX) root.tex
	$(BIBTEX) root
	$(PDFLATEX) root.tex
	$(PDFLATEX) root.tex
	mv root.pdf $@

slide_deck.pdf: slide_deck.tex figures/*.eps
	$(PDFLATEX) slide_deck.tex
	$(PDFLATEX) slide_deck.tex

.PHONY: all clean
