DOCUMENTS = report.pdf
PDFLATEX = pdflatex
BIBTEX = bibtex

all: $(DOCUMENTS)
	

clean:
	rm -rf $(DOCUMENTS) *.aux *.log *.bbl *.blg

report.pdf: root.tex root.bib
	$(PDFLATEX) root.tex
	$(BIBTEX) root
	$(PDFLATEX) root.tex
	$(PDFLATEX) root.tex
	mv root.pdf $@

.PHONY: all clean
