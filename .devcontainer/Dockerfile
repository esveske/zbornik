FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Belgrade

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
  && useradd -s /usr/bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME 

RUN apt-get update && \
    ln -fs /usr/share/zoneinfo/Europe/Belgrade /etc/localtime && \
    echo "Europe/Belgrade" > /etc/timezone && \
    apt-get install -y tzdata && \
    dpkg-reconfigure -f noninteractive tzdata

RUN echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get update && apt-get install -y \
    texlive \
    git \
    gnuplot \
    latexmk \
    build-essential \
    texlive-xetex \
    texlive-science \
    fonts-freefont-ttf \
    ttf-mscorefonts-installer \
    wget \
    texlive-latex-extra \
    texlive-lang-cyrillic \
    texlive-full \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* && \
    wget https://mirrors.ctan.org/macros/latex/contrib/algpseudocodex/algpseudocodex.sty && \
    mkdir -p ~/texmf/tex/latex/algpseudocodex && \
    mv algpseudocodex.sty ~/texmf/tex/latex/algpseudocodex/ && \
    texhash ~/texmf


CMD ["bash"]