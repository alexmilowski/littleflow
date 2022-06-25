PDF_ENGINE := pdflatex
PANDOC_FILTERS := --filter pandoc-fignos
all: flowalg.pdf

flowalg.pdf: flowalg.md
	pandoc -f markdown+smart flowalg.md --citeproc -t pdf -o flowalg.pdf --pdf-engine ${PDF_ENGINE} --template ../acm.latex ${PANDOC_FILTERS}
