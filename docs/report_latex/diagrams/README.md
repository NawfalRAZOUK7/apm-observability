# Diagrams (PlantUML)

These .puml files can be rendered to PNG using PlantUML.

Example command:

```
plantuml -tpng docs/report_latex/diagrams/*.puml
```

Docker alternative:

```
docker run --rm -v "$PWD":/work -w /work plantuml/plantuml \
  -tpng docs/report_latex/diagrams/*.puml -o ../images
```

If you prefer Mermaid or Graphviz, tell me and I can convert them.
