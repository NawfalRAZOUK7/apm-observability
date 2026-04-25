\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{apm_report}[2025/12/28 APM academic report class]

\LoadClass[12pt,a4paper]{article}

% Core packages
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[french]{babel}
\RequirePackage{geometry}
\RequirePackage{graphicx}
\RequirePackage{float}
\RequirePackage{booktabs}
\RequirePackage{url}
\RequirePackage{hyperref}
\RequirePackage{xcolor}
\RequirePackage{tikz}
\RequirePackage{fancyhdr}
\RequirePackage{titlesec}
\RequirePackage{listings}
\RequirePackage{array}
\RequirePackage{lmodern}
\RequirePackage{microtype}

% Page geometry
\geometry{margin=2.5cm}

% Colors (academic, high contrast)
\definecolor{apm-primary}{HTML}{0B1F3A}
\definecolor{apm-primary-dark}{HTML}{071427}
\definecolor{apm-accent}{HTML}{C89B2B}
\definecolor{apm-accent-soft}{HTML}{F1E2BD}
\definecolor{apm-light}{HTML}{FBF9F4}
\definecolor{apm-text}{HTML}{1C1C1C}
\definecolor{apm-muted}{HTML}{515151}

% Hyperlinks
\hypersetup{
    colorlinks=true,
    linkcolor=apm-primary,
    citecolor=apm-primary,
    urlcolor=apm-primary
}

% Section styling (serif)
\renewcommand{\thesection}{\Roman{section}}
\renewcommand{\thesubsection}{\thesection.\arabic{subsection}}
\renewcommand{\thesubsubsection}{\thesubsection.\arabic{subsubsection}}
\titleformat{\section}{\Large\bfseries\color{apm-primary}}{Chapitre \thesection}{0.6em}{}
\titleformat{\subsection}{\large\bfseries\color{apm-text}}{\thesubsection}{0.6em}{}
\titleformat{\subsubsection}{\normalsize\bfseries\color{apm-text}}{\thesubsubsection}{0.6em}{}

% Listings style
\lstdefinestyle{apm}{
    basicstyle=\ttfamily\small,
    breaklines=true,
    frame=single,
    columns=fullflexible,
    showstringspaces=false,
    tabsize=2
}
\lstset{style=apm}

\makeatletter
% Report metadata (defaults)
\newcommand{\reporttitle}[1]{\def\apm@title{#1}}
\newcommand{\reportsubtitle}[1]{\def\apm@subtitle{#1}}
\newcommand{\reportauthor}[1]{\def\apm@author{#1}}
\newcommand{\reportinstitute}[1]{\def\apm@institute{#1}}
\newcommand{\reportsupervisor}[1]{\def\apm@supervisor{#1}}
\newcommand{\reportdegree}[1]{\def\apm@degree{#1}}
\newcommand{\reportlocation}[1]{\def\apm@location{#1}}
\newcommand{\reportdate}[1]{\def\apm@date{#1}}
\newcommand{\reporttype}[1]{\def\apm@type{#1}}
\newcommand{\reportlogo}[1]{\def\apm@logo{#1}}
\newcommand{\reportproject}[1]{\def\apm@project{#1}}
\newcommand{\reportcourse}[1]{\def\apm@course{#1}}
\newcommand{\reporttopic}[1]{\def\apm@topic{#1}}
\newcommand{\apm@multiline}[1]{\begin{tabular}[t]{@{}l@{}}#1\end{tabular}}

\reporttitle{Titre du rapport}
\reportsubtitle{Sous-titre}
\reportauthor{Nom Prenom}
\reportinstitute{Etablissement / Organisation}
\reportsupervisor{Encadrant}
\reportdegree{Diplome / Parcours}
\reportlocation{Ville, Pays}
\reportdate{\today}
\reporttype{Rapport academique et professionnel}
\reportlogo{}
\reportproject{}
\reportcourse{}
\reporttopic{}

% Header / footer
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\sectionmark}[1]{\markright{#1}}
\renewcommand{\subsectionmark}[1]{}
\renewcommand{\subsubsectionmark}[1]{}
\fancyhead[L]{\small\scshape\ifx\apm@project\@empty\apm@title\else\apm@project\fi}
\fancyhead[R]{\small\scshape \nouppercase{\rightmark}}
\newcommand{\apm@footline}{%
    \begin{tikzpicture}[baseline=(n.base)]
        \draw[apm-primary,line width=0.4pt] (-0.46\linewidth,0) -- (0.46\linewidth,0);
        \node[draw,circle,inner sep=2pt,fill=apm-light,line width=0.4pt] (n) {\footnotesize\thepage};
    \end{tikzpicture}%
}
\fancyfoot[C]{\apm@footline}
\setlength{\headheight}{14pt}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}

% Custom cover page
\newlength{\apm@coverband}
\setlength{\apm@coverband}{2.4cm}
\newlength{\apm@coverindent}
\setlength{\apm@coverindent}{3.0cm}
\newlength{\apm@titlewidth}

\renewcommand{\maketitle}{
    \begin{titlepage}
        \thispagestyle{empty}
        \begin{tikzpicture}[remember picture,overlay]
            \fill[apm-light] (current page.north west) rectangle (current page.south east);
            \shade[top color=apm-primary, bottom color=apm-primary-dark]
                (current page.north west) rectangle ([xshift=\apm@coverband]current page.south west);
            \fill[apm-accent] ([xshift=0.56\paperwidth]current page.north west) --
                              (current page.north east) --
                              ([xshift=0.92\paperwidth,yshift=-5.6cm]current page.north west) -- cycle;
            \fill[apm-accent-soft] ([xshift=0.50\paperwidth,yshift=-2.2cm]current page.north west) circle (1.05cm);
            \ifx\apm@logo\@empty
            \else
                \node[anchor=north east, xshift=-1.6cm, yshift=-1.6cm]
                    at (current page.north east) {\includegraphics[width=2.6cm]{\apm@logo}};
            \fi
        \end{tikzpicture}

        \vspace*{2.4cm}
        \noindent
        \hspace*{\apm@coverindent}%
        \begin{minipage}[t]{\dimexpr\textwidth-\apm@coverindent\relax}
            {\color{apm-primary}\Large\textsc{\apm@type}}\\[0.8em]
            \settowidth{\apm@titlewidth}{\bfseries\huge \apm@title}
            \ifdim\apm@titlewidth>\linewidth
                \settowidth{\apm@titlewidth}{\bfseries\LARGE \apm@title}
                \ifdim\apm@titlewidth>\linewidth
                    {\color{apm-primary-dark}\Large\bfseries \apm@title}\\[0.3em]
                \else
                    {\color{apm-primary-dark}\LARGE\bfseries \apm@title}\\[0.3em]
                \fi
            \else
                {\color{apm-primary-dark}\huge\bfseries \apm@title}\\[0.3em]
            \fi
            {\color{apm-muted}\Large\itshape \apm@subtitle}\\[1.1em]

            {\color{apm-accent}\rule{0.30\textwidth}{2.6pt}}\\[1.2em]

            {\color{apm-text}\normalsize
            \renewcommand{\arraystretch}{1.15}
            \begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.24\linewidth}@{\hspace{0.6em}}>{\raggedright\arraybackslash}p{0.72\linewidth}}
                \ifx\apm@project\@empty\else \textbf{Projet:} & \apm@project \\ \fi
                \ifx\apm@course\@empty\else \textbf{Matiere:} & \apm@course \\ \fi
                \ifx\apm@topic\@empty\else \textbf{Sujet:} & \apm@topic \\ \fi
                \textbf{Auteur:} & \apm@multiline{\apm@author} \\
                \textbf{Encadrant:} & \apm@supervisor \\
                \textbf{Formation:} & \apm@degree \\
                \textbf{Institution:} & \apm@institute \\
            \end{tabular}}
        \end{minipage}
        \vfill
        \noindent
        \hspace*{\apm@coverindent}%
        \begin{minipage}[t]{0.45\textwidth}
            {\color{apm-text}\normalsize \apm@location}\\[0.2em]
            {\color{apm-text}\normalsize \apm@date}
        \end{minipage}
        \vspace{0.6cm}
        \begin{center}
            {\color{apm-primary}\rule{0.68\textwidth}{1.6pt}}\\[0.6em]
            {\color{apm-muted}\small Observability \textbullet\ TimescaleDB \textbullet\ Grafana}
        \end{center}
    \end{titlepage}
}
\makeatother
