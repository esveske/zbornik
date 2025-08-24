\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{sveska}[2022/07/09 Petnica Papers style]

\LoadClass[10pt, twoside, serbian]{report}

\RequirePackage{fontspec}
\RequirePackage{color}
\RequirePackage{pdfpages}

\RequirePackage[
    b5paper,
    left=19mm, 
    right=41.7mm, 
    top=21.9mm,
    bottom=22mm,
    marginparwidth=32mm,
    marginparsep=3.2mm,
    asymmetric
]{geometry}

\RequirePackage{atbegshi}
\RequirePackage{zref-abspage}
\RequirePackage{picture}
\RequirePackage{environ}
\RequirePackage{titlesec}
\RequirePackage{fancyhdr}
\RequirePackage{multicol}
\RequirePackage{graphicx}
\RequirePackage{float}
\RequirePackage{enumitem}
\RequirePackage{algorithm}
\RequirePackage[indLines=false]{algpseudocodex}
\RequirePackage{wrapfig}
\RequirePackage{subcaption}
\RequirePackage{amsmath}
\RequirePackage{import}
\RequirePackage{multirow}
\RequirePackage{amsthm}
\RequirePackage{booktabs,multicol, multirow,boldline,makecell}
\RequirePackage[absolute,overlay]{textpos}
\RequirePackage{longtable} % pandoc output
\RequirePackage[normalem]{ulem} % pandoc output
\newcommand{\ul}[1]{\uline{#1}}

\RequirePackage[serbian, english]{babel}
\RequirePackage{csquotes} % Package biblatex Warning: 'babel/polyglossia' detected but 'csquotes' missing.

\newcommand\captionmainlanguage{serbian}
\RequirePackage[lang=english]{bicaption}

% VHRULEFILL
\def\vhrulefill#1{\leavevmode\leaders\hrule\@height#1\hfill \kern\z@}

% MARGIN THING

\providecommand*{\c@zabspage}{\c@abspage}

% * User macros for configuring
%
% \tbmparItemSep is inserted between marginal notes
% \tbmparMiddleSep is inserted between top and bottom marginal notes.

\newcommand*{\tbmparItemSep}{%
  \vspace{1ex minus .5ex}%
  \hrule
  \vspace{1ex minus .5ex}%
}
\newcommand*{\tbmparMiddleSep}{%
  \vspace*{0pt plus 1fil}%
}

% * Debug messages
%
\newcommand*{\tbmparDebug}[1]{%
  \typeout{[tbmpar] #1}%
}

% * Label management to remember absolute page number
%
% \tbmpar@PageByLabel stores and loads absolute page number from
% label and defines \tbmpar@page with absolute page number or
% zero if the label is not yet available.

\newcount\c@tbmpar@item
\c@tbmpar@item\z@

\newcommand*{\tbmpar@PageByLabel}{%
  \global\advance\c@tbmpar@item\@ne
  \zref@labelbyprops{tbmpar\the\c@tbmpar@item}{abspage}%
  \edef\tbmpar@page{%
    \zref@extractdefault{tbmpar\the\c@tbmpar@item}{abspage}{0}%
  }%
  \zref@refused{tbmpar\the\c@tbmpar@item}%
  \tbmparDebug{Item \the\c@tbmpar@item\space on page \tbmpar@page}%
}

% * Box register management

\newcount\c@tbmpar@box
\c@tbmpar@box\z@

\let\tbmpar@boxfreelist\@empty

% Get a new free box register either from the free list or,
% if the free list is empty, allocate a new box register.
\newcommand*{\tbmpar@NextBox}[1]{%
  \@next#1\tbmpar@boxfreelist{%  
    \tbmparDebug{Reused box: #1}%
  }{%
    \global\advance\c@tbmpar@box\@ne
    \expandafter\newbox\csname tbmpar@box\the\c@tbmpar@box\endcsname
    \edef#1{\csname tbmpar@box\the\c@tbmpar@box\endcsname}%
    \tbmparDebug{New box: #1}%
  }%
}
% Put free box in free list.
\newcommand*{\tbmpar@FreeBox}[1]{%
  \begingroup
    \let\@elt\relax
    \xdef\tbmpar@boxfreelist{%
      \tbmpar@boxfreelist
      \@elt#1%
    }%
    \tbmparDebug{Free box: #1}%
  \endgroup
}

\newsavebox{\tbmpar@box}

% Each marginpar is put in a box that is initialized as
% parbox/minipage.
\newcommand*{\tbmparBoxSetup}{}
\newcommand{\tbmpar@VBox}[1]{% 
  \vbox{%
    \color@begingroup
    \hsize\marginparwidth
    \edef\tbmpar@restore@ifminipage{%
      \if@minipage
        \noexpand\@minipagetrue
      \else
        \noexpand\@minipagefalse
      \fi
    }%   
    \@parboxrestore
    \@marginparreset
    \tbmparBoxSetup 
    #1%
    \tbmpar@restore@ifminipage
    \color@endgroup
  }%
}   

% Macro \tbmpar@marginpar looks for the page, where the margin note
% belongs to, stores the note in a box and appends the box to the  
% note collector register of the page.
% Each page is assigned a box collector registers that collect
% the top notes and a register that collect the bottom notes. 
% The name of the box register is \tbmpar@<top|bot>box<page>. 
\newcommand{\tbmpar@marginpar}[4]{%
  \ifhmode
    \@bsphack
  \fi
  \tbmpar@PageByLabel
  \ifnum\tbmpar@page>\z@
    \setbox\tbmpar@box\tbmpar@VBox{#4}%
    \@ifundefined{tbmpar@#1box\tbmpar@page}{%
      \tbmpar@NextBox\tbmpar@currbox
      \global\expandafter\let
          \csname tbmpar@#1box\tbmpar@page\endcsname
          \tbmpar@currbox
      \global\setbox\tbmpar@currbox=\vbox{%
        \unvbox\tbmpar@box
      }%
    }{% 
      \tbmparDebug{Use box: \tbmpar@currbox}%
      \expandafter\let\expandafter\tbmpar@currbox
          \csname tbmpar@#1box\tbmpar@page\endcsname
      \global\setbox\tbmpar@currbox\tbmpar@VBox{%   
        \unvbox#2%
        \par
        \begingroup
          \tbmparItemSep
        \endgroup
        \unvbox#3%
      }%
    }%  
  \fi   
  \ifhmode
    \@esphack
  \fi
}
\newcommand*{\topmarginpar}{%
  \tbmpar@marginpar{top}\tbmpar@currbox\tbmpar@box
}
\newcommand*{\botmarginpar}{%
  \tbmpar@marginpar{bot}\tbmpar@box\tbmpar@currbox
}

% At shipout time we look for the box collector registers of this
% page and set these boxes in the marginpar box with respecting  
% \topskip and \maxdepth.
\AtBeginShipout{%
  \AtBeginShipoutUpperLeft{%
    \put(%
      \dimexpr 1in+\oddsidemargin+\textwidth+\marginparsep\relax,%
      -\dimexpr 1in+\topmargin+\headheight+\headsep+\textheight\relax
    ){%
      \begingroup
        \global\let\tbmpar@inuse=N%
        \setbox\tbmpar@box=\tbmpar@VBox{%
          \penalty-\@M
          \edef\tbmpar@tmp{tbmpar@topbox\the\value{zabspage}}%
          \@ifundefined{\tbmpar@tmp}{%
          }{%
            \expandafter\let\expandafter\tbmpar@currbox
                \csname\tbmpar@tmp\endcsname
            \unvbox\tbmpar@currbox
            \tbmpar@FreeBox\tbmpar@currbox
            \global\let\tbmpar@inuse=Y%   
          }%
          \endgraf
          \tbmparMiddleSep
          \edef\tbmpar@tmp{tbmpar@botbox\the\value{zabspage}}%
          \@ifundefined{\tbmpar@tmp}{%
          }{%
            \expandafter\let\expandafter\tbmpar@currbox
                \csname\tbmpar@tmp\endcsname
            \unvbox\tbmpar@currbox
            \tbmpar@FreeBox\tbmpar@currbox
            \global\let\tbmpar@inuse=Y%   
          }%
        }%  
        \ifx\tbmpar@inuse Y%
          \splittopskip=\topskip
          \setbox0=\vsplit\tbmpar@box to\z@
          \boxmaxdepth=\maxdepth
          \setbox\tbmpar@box=\vbox to\textheight{%
            \unvbox\tbmpar@box
          }%
          \box\tbmpar@box
        \fi
      \endgroup
    }%
  }%  
}     

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\def\Year#1{\gdef\@Year{#1}}
\gdef\@Year{\ClassError{sveska}{Year not defined}}%
\def\BookNumber#1{\gdef\@BookNumber{#1}}
\gdef\@BookNumber{\ClassError{sveska}{BookNumber not defined}}%

\def\Part#1{\gdef\@Part{#1}}
\gdef\@Part{\ClassError{sveska}{Part not defined}}%
\def\Section#1{\gdef\@Section{#1}}
\gdef\@Section{SECTION-TODO}%\ClassError{sveska}{Section not defined}}%

\def\Title#1{\gdef\@Title{#1}}
\def\TitleEng#1{\gdef\@TitleEng{#1}}
\def\Author#1{\gdef\@Author{#1}}
\NewEnviron{Abstract}{\xdef\@Abstract{\BODY}}
\NewEnviron{AbstractEng}{\xdef\@AbstractEng{\BODY}}
\NewEnviron{AuthorEx}{\xdef\@AuthorEx{\BODY}}

\def\Clear@Title{%
\gdef\@Title{\ClassError{sveska}{Title not defined}}%
\gdef\@TitleEng{\ClassError{sveska}{TitleEng not defined}}%
\gdef\@Author{\ClassError{sveska}{Author not defined}}%
\gdef\@Abstract{\ClassError{sveska}{Abstract not defined}}%
\gdef\@AbstractEng{\ClassError{sveska}{AbstractEng not defined}}%
\gdef\@AuthorEx{\ClassError{sveska}{AuthorEx not defined}}%
}

\Clear@Title

% author box that floats to the bottom, in twocol papers
% it should be made so that it also goes to the right column
% but this will often leave a 
\newfloat{auth@float}{b}{authfloat}

\newenvironment{auth@floatp}{\if@firstcolumn\newpage\leavevmode\fi
\auth@float}{\endauth@float}

\newcommand{\SectionCover}[5]{
    \pagestyle{empty}
    \newgeometry{
        left=15mm, 
        right=15mm, 
        top=21.9mm,
        bottom=22mm,
        asymmetric
    }
    
    \vspace*{\fill}
    
    \begin{figure}[h!]\centering
    \begin{subfigure}[b]{0.3\textwidth}
      \vspace*{\fill}
      \hspace{\fill}\includegraphics[width=0.2\textwidth]{graphics/sigil.png}
    \end{subfigure}\hfill%
    \begin{subfigure}[b]{0.6\textwidth}
      {\sffamily\fontsize{48pt}{52pt}\selectfont #1}
    \end{subfigure}
    \end{figure}
    
    \vspace{5mm}
    
    \begin{figure}[h!]
    \centering
    \begin{subfigure}[t]{0.3\textwidth}
    \vspace{0pt}
     \begin{flushright}
        {\Tekton\selectfont #3

         \vspace{15mm}

         #4}
     \end{flushright}
    \end{subfigure}\hfill%
    \begin{subfigure}[t]{0.6\textwidth}
    \vspace{0pt}
     #5
    \end{subfigure}
    \end{figure}
    
    \vspace{\fill}
    
    {
        \centering
        \sffamily\fontsize{18pt}{22pt}\selectfont
        \vbox{#2}
    }
    \clearpage
    \pagestyle{fancy} 
}

\newcommand{\Start@Common}{
    \setcounter{equation}{0}
    \setcounter{figure}{0}
    \setcounter{table}{0}
    \setcounter{Theorem}{0}
    \setcounter{Example}{0}
    \setcounter{Proposition}{0}
    \setcounter{Corollary}{0}
    \setcounter{Definition}{0}

}

\newcommand{\StartPaper}{
    \newgeometry{
        left=19mm, 
        right=41.7mm, 
        top=21.9mm,
        bottom=22mm,
        marginparwidth=32mm,
        marginparsep=3.2mm,
        asymmetric
    }
    \onecolumn
    \fancyfootoffset[R]{30mm}
    \Start@Common
    
    \noindent \vhrulefill{1mm}
    \begin{textblock*}{\linewidth}(19mm, 27.5mm)
       \noindent \fontsize{12pt}{14pt}\selectfont \textit{\@Author}
    \end{textblock*}
    \begin{textblock*}{\linewidth}(19mm, 37.1mm)
        \noindent \fontsize{20pt}{22pt}\selectfont \raggedright \@Title % 20pt
    \end{textblock*}
    
    \vspace{53mm}
    \noindent \hrulefill\\
    \noindent \textit{\@Abstract}
    
    \noindent \vhrulefill{0.5mm}
    
    \botmarginpar{
        \parskip=10pt
        \hrulefill\\
        \raggedright \textit{\@AuthorEx}}
}

\newcommand{\StartDoublePaper}{
    \newgeometry{
        left=15mm, 
        right=15mm, 
        top=21.9mm,
        bottom=22mm,
        asymmetric
    }
    \twocolumn
    \fancyfootoffset[R]{0pt}
    \Start@Common
    
    \noindent \vhrulefill{1mm}
    \begin{textblock*}{\linewidth}(15mm, 27.5mm)
       \noindent \fontsize{11pt}{13pt}\selectfont \textit{\@Author}
    \end{textblock*}
    \begin{textblock*}{\linewidth}(15mm, 37.1mm)
        \noindent \fontsize{18pt}{20pt}\selectfont \raggedright \@Title % 20pt
    \end{textblock*}
    
    \vspace{53mm}
    \noindent \hrulefill\\
    \noindent \textit{\@Abstract}
    
    \noindent \vhrulefill{0.5mm}
}

% must be placed somewhere in the right column of twocol papers
\newcommand{\AuthorExHere}{
    \begin{auth@float}
        \parskip=10pt
        % \hrulefill\
        \raggedright \textit{\@AuthorEx}
    \end{auth@float}
}

\RequirePackage[backend=biber,style=authoryear,language=serbian]{biblatex}
\newcommand{\Source}[1]{%
\vbox{\noindent{}#1}
\vspace{3mm}
}

\newcommand{\EndPaper}{
    \vspace{7mm}
    \vspace*{-7mm}
    \noindent\vhrulefill{0.5mm}\\
    {\fontsize{11pt}{13pt}\selectfont{}\textit{\@Author}}\\[3mm]%
    \selectlanguage{english}{\fontsize{13pt}{15pt}\selectfont \raggedright \@TitleEng}

    \vspace{3mm}
    \@AbstractEng
    \selectlanguage{serbian}
    \Clear@Title
}

\renewcommand{\headrulewidth}{0pt}

\setmainfont{Times New Roman}
\titleformat{\section}{\normalfont\fontsize{16pt}{19pt}\selectfont}{\thesection}{1em}{}
\titleformat{\subsection}{\normalfont\fontsize{13pt}{16pt}\selectfont}{\thesubsection}{1em}{}
\titleformat{\subsubsection}{\normalfont\fontsize{11pt}{14pt}\selectfont}{\thesubsubsection}{1em}{}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot[LE]{{\sffamily{}\small \thepage\ $\bullet$\ PETNIČKE SVESKE \@BookNumber}}
\fancyfoot[RE]{{\sffamily{}\small DEO \@Part}}
\fancyfoot[LO]{{\sffamily{}\small ZBORNIK RADOVA \@Year}}
\fancyfoot[RO]{{\sffamily{}\small \@Section\ $\bullet$\ \thepage}}


%%%%%%%%%%%%%% figures

\newcommand{\Figure}[4]{
    \begin{figure}
        \centering
        \includegraphics[width=\linewidth]{#1}
        \bicaption{#2}{#3}
    \end{figure}
}

\newcommand{\FigureDouble}[4]{
    \begin{figure*}
        \centering
        \includegraphics[width=\linewidth]{#1}
        \bicaption{#2}{#3}
    \end{figure*}
}

\newcommand{\Table}[4]{
    \begin{table}
        \centering
        #1
        \bicaption{#2}{#3}
    \end{table}
}

\newcommand{\TableDouble}[4]{
    \begin{table*}
        \centering
        #1
        \bicaption{#2}{#3}
    \end{table*}
}

\DeclareBiCaptionSeparator{hrule}{\vspace{-1ex}\noindent\rule{36mm}{0.075mm}\\}
\captionsetup{bi-separator=hrule,justification=raggedright,singlelinecheck=false,labelsep=period}

%%%%%%%%%%%%%% Mathematics 

\newtheorem{Theorem}{Teorema}
\newtheorem{Corollary}{Posledica}
\newtheorem{Definition}{Definicija}
\newtheorem{Proposition}{Tvrđenje}
\newtheorem{Example}{Primer}
\newtheorem{Lemma}{Lema}
% \renewcommand*{\proofname}{Dokaz}
\newenvironment{Proof}{
  \begin{proof}
}{
  \end{proof}
}
%%%%%%%%%%%%%%%%%% no numberings

\setcounter{secnumdepth}{0}

\setlist[itemize]{leftmargin=*}

\newfontfamily\Tekton{tekton.ttf}

\floatname{algorithm}{Algoritam}

\DeclareMathOperator*{\argmax}{arg\,max}
\DeclareMathOperator*{\argmin}{arg\,min}

\setlocalecaption{serbian}{table}{Tabela}

\sloppy
