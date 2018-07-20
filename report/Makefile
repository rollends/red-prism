DOCUMENTS = report.pdf
PDFLATEX = pdflatex
BIBTEX = bibtex

all: $(DOCUMENTS)
	

clean:
	rm -rf $(DOCUMENTS) *.aux *.log *.bbl *.blg

report.pdf: root.tex
	$(PDFLATEX) root.tex
	$(BIBTEX) root
	$(PDFLATEX) root.tex
	mv root.pdf $@

.PHONY: all clean
