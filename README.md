- [Uvod](#uvod)
- [Uputstvo za rad na zborniku radova](#uputstvo-za-rad-na-zborniku-radova)
  - [Razvojni režim (Dev Mode)](#razvojni-režim-dev-mode)
    - [Opcija A: Korišćenje **GitHub Codespace**](#opcija-a-korišćenje-github-codespace)
      - [Napravite GitHub nalog](#napravite-github-nalog)
      - [Zatražite pristup repozitorijumu](#zatražite-pristup-repozitorijumu)
      - [Otvorite Codespace](#otvorite-codespace)
    - [Opcija B: Korišćenje VS Code + Docker na svom računaru](#opcija-b-korišćenje-vs-code--docker-na-svom-računaru)
      - [Instalirajte Visual Studio Code](#instalirajte-visual-studio-code)
      - [Instalirajte Docker Desktop](#instalirajte-docker-desktop)
      - [Klonirajte repozitorijum](#klonirajte-repozitorijum)
      - [Pokrenite razvojno okruženje (devcontainer)](#pokrenite-razvojno-okruženje-devcontainer)
  - [Generisanje PDF-a](#generisanje-pdf-a)
  - [Kontakt](#kontakt)
- [Pisanje radova](#pisanje-radova)
  - [Gde početi?](#gde-početi)
  - [Komande](#komande)
  - [Naslovna strana programa](#naslovna-strana-programa)
  - [Pojedinacni rad](#pojedinacni-rad)
  - [Zamene za LaTeX komande](#zamene-za-latex-komande)
  - [Slanje rada putem **Pull Request-a (PR)**](#slanje-rada-putem-pull-request-a-pr)
    - [Otvorite repozitorijum](#otvorite-repozitorijum)
    - [Napravite novu granu (branch)](#napravite-novu-granu-branch)
    - [Napravite i uredite svoj rad](#napravite-i-uredite-svoj-rad)
    - [Testirajte generisanje PDF-a](#testirajte-generisanje-pdf-a)
    - [Sačuvajte promene (Commit)](#sačuvajte-promene-commit)
    - [Pošaljite granu (Push)](#pošaljite-granu-push)
    - [Napravite Pull Request (PR)](#napravite-pull-request-pr)
- [Često postavljana pitanja (FAQ)](#često-postavljana-pitanja-faq)
  - [Nikada nisam radio/la u LaTeX-u. Da li mogu da učestvujem?](#nikada-nisam-radiola-u-latex-u-da-li-mogu-da-učestvujem)
  - [Mogu li raditi sa Windows / macOS / Linux računara?](#mogu-li-raditi-sa-windows--macos--linux-računara)
  - [Kako predajem rad?](#kako-predajem-rad)
  - [Šta ako mi se PDF ne generiše ili dobijem grešku?](#šta-ako-mi-se-pdf-ne-generiše-ili-dobijem-grešku)
  - [Mogu li više osoba raditi zajedno na jednom radu?](#mogu-li-više-osoba-raditi-zajedno-na-jednom-radu)
  - [Šta ako ne stignem sve da završim odjednom?](#šta-ako-ne-stignem-sve-da-završim-odjednom)
  - [Ostalo ...](#ostalo-)


# Uvod 

Dobrodošli u repozitorijum namenjen pripremi **zbornika radova** u okviru redovnog **Petničkog ciklusa** u **Istraživačkoj stanici Petnica**.

Cilj ovog projekta je da se svi polaznički radovi pripreme u ujednačenom i profesionalnom formatu, koristeći **LaTeX** kao standard za tehničku i naučnu dokumentaciju. Ovaj repozitorijum pruža alate i okruženje koje omogućava:

- Jedinstven vizuelni i strukturni stil svih radova
- Lakšu saradnju među mentorima, polaznicima i urednicima
- Automatsko generisanje PDF-ova iz koda (LaTeX)
- Kontrolu verzija i jednostavno predavanje gotovih radova

> Bez obzira na to da li ste iskusan istraživač ili vam je ovo prvi kontakt sa sličnim alatima – **dobrodošli ste da doprinesete!** Trudili smo se da sve bude jasno i jednostavno, uz detaljna uputstva korak po korak.

Ovaj radni prostor ne samo da olakšava tehnički deo pripreme rada, već pruža i priliku da naučite kako se profesionalni dokumenti pripremaju u istraživačkom i akademskom svetu.

# Uputstvo za rad na zborniku radova

Dobrodošli! Ovaj repozitorijum omogućava zajednički rad na zborniku radova, gde se svaki rad piše u LaTeX-u. Da biste radili na svom radu, potrebno je da otvorite razvojno okruženje (dev environment), napišete rad i generišete PDF pomoću jednostavne komande.

Ovo uputstvo opisuje **dva načina rada**:

1. **GitHub Codespaces** – rad direktno u internet pregledaču (laptop ili desktop)
2. **VS Code + Docker** – lokalna instalacija potrebnih alata na vašem računaru



## Razvojni režim (Dev Mode)

### Opcija A: Korišćenje **GitHub Codespace**

Ovo je najlakši način jer ne zahteva instalaciju alata na vašem računaru. Sve se radi u internet pregledaču, ali napomena: **GitHub Codespaces se naplaćuju nakon besplatne kvote.**

#### Napravite GitHub nalog

1. Idite na [https://github.com](https://github.com)
2. Kliknite na dugme **"Sign up"**
3. Pratite uputstva da biste napravili nalog

#### Zatražite pristup repozitorijumu

Pošaljite vaš GitHub korisnički naziv osobi koja upravlja projektom, kako bi Vam se dodelio pristup.

#### Otvorite Codespace

1. Posetite stranicu repozitorijuma
2. Kliknite na zeleno dugme **Code**
3. Izaberite karticu **Codespaces**
4. Kliknite na dugme **"Create codespace on main"**

**Napomena:** Prvo pokretanje može potrajati nekoliko minuta. Koristite stabilnu internet konekciju.

**Napomena o naplati** GitHub Codespaces ima besplatnu kvotu (60 sati mesečno za lične naloge). Nakon toga, vreme provedeno u codespace-u se naplaćuje.

### Opcija B: Korišćenje VS Code + Docker na svom računaru

Preporučeno ako ne želite da koristite Codespaces ili radite bez internet konekcije.

#### Instalirajte Visual Studio Code

1. Idite na [https://code.visualstudio.com](https://code.visualstudio.com)
2. Kliknite na **"Download for Windows"** (ili vaš operativni sistem)
3. Instalirajte program kao bilo koju drugu aplikaciju

#### Instalirajte Docker Desktop

1. Idite na [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Preuzmite verziju za vaš sistem
3. Instalirajte i restartujte računar ako se to zatraži
4. Pokrenite Docker Desktop – ikonica u donjem desnom uglu treba da bude **zelena**

#### Klonirajte repozitorijum

1. Otvorite VS Code
2. Otvorite **Command Palette** (`Ctrl + Shift + P`)
3. Ukucajte **"Git: Clone"** i pritisnite Enter
4. Nalepite URL repozitorijuma (dobijate ga sa GitHub stranice, klikom na **Code > HTTPS** kopirajte link)
5. Odaberite folder na vašem računaru

#### Pokrenite razvojno okruženje (devcontainer)

1. Kada se repozitorijum otvori u VS Code-u, pojaviće se pitanje:
   ```
   "This folder contains a Dev Container configuration file. Reopen in Container?"
   ```
2. Kliknite **"Reopen in Container"**

Ako ne dobijete pitanje:

- Otvorite Command Palette (`Ctrl + Shift + P`)
- Ukucajte i izaberite: `Dev Containers: Reopen in Container`

Prvo pokretanje traje nekoliko minuta dok se priprema okruženje.


## Generisanje PDF-a

Kada ste unutar dev okruženja (bilo preko Codespace-a ili lokalno):

1. Otvorite **Terminal**:
   - `Ctrl + `` (backtick)`, ili
   - Kliknite na **Terminal > New Terminal** u meniju

2. Pokrenite komandu:

```bash
make
```

1. Ako nema grešaka, pojaviće se PDF verzija zbornika.


## Kontakt

Ako imate bilo kakvih problema:

- Obratite se organizatorima projekta
- Pošaljite poruku ili email osobi koja vam je dodelila pristup


# Pisanje radova 

Radove je potrebno pisati u LaTeX-u, koji je standard za profesionalnu pripremu naučnih i tehničkih dokumenata.

## Gde početi?

1. U repozitorijumu postoji folder `2020/` koji sadrži primere prethodnih radova.
2. Najbolji način da počnete je da **kopirate neki od postojećih radova** i zamenite sadržaj svojim.
3. Svaki rad je organizovan kao `.tex` fajl, često sa dodatnim `.gnu` fajlom (za grafikone), i eventualno slikama.

Preporučuje se sledeće:
- Ne menjajte `Makefile`
- Ne menjajte podešavanja stila (`.cls`, `.sty`) osim ako nije dogovoreno
- Radove stavite u sopstveni folder, npr. `2025/seminar/redniBroj_ime_prezime/main.tex`


## Komande

Komende koje zapocinju delove sveske. Ove komande iskljucivo uticu na podnozje stranice.

* `\Year{<yr>}` - definise godinu izdavanja zbornika, npr. `\Year{2021}`
* `\BookNumber{<num>}` - definise broj sveske, npr. `\BookNumber{80}`
* `\Part{<num>}` - definise deo (odeljenje), npr. `\Part{I}`, `\Part{II}`, ...
* `\Section{<sec>}` - definise trenutni program, npr. `\Section{RAČUNARSTVO}`

## Naslovna strana programa

Za pravljenje naslovne strane jednog programa, koristi se komanda `\SectionCover`. Ova komanda prima pet parametara:

```latex
\SectionCover{
    <ime programa na srpskom>
}{
    <ime programa na engleskom>
}{
    <sadrzaj radova sa programa>
}{
    <imena rukovodioca>
}{
    <grafika programa>
}
```

Na primer, kompletna naslovna stranica programa izgleda ovako:

```latex
\Section{RAČUNARSTVO}

\pagestyle{empty} % na naslovnij stranici programa nema numeracije
\SectionCover{Računarstvo}{Computer\\Science}{
    Autor 1 \pageref{rac.autor1}\\
    Autor 2 \pageref{rac.autor2}\\
}{
    RUKOVODIOCI:\\
    Rukovodioc 1\\
    Rukovodioc 2
}{
    % grafika za naslovnu stranicu
    \includegraphics[width=\textwidth]{graphics/mce-white-cat.png}
}
\clearpage

\pagestyle{fancy} % nastavljanje numeracije
% import-i pojedinacnih radova
```

## Pojedinacni rad

Sledece komande definisu podatke o radu. Nista zapravo ne ispisuju.

* `\Title{<naslov>}` - definise nasov rada
* `\TitleEng{<naslov>}` - definise naslov rada na engleskom
* `\Author{<autor(i)>}` - definise autore rada, odvojene zarezom
* `\begin{Abstract}...\end{Abstract}` - definise apstrakt na srpskom jeziku
* `\begin{AbstractEng}...\end{AbstractEng}` - definise apstrakt na engleskom jeziku
* `\begin{AuthroEx}...\end{AuthorEx}` - definise dodatne podatke o autoru i mentorima.

Sledece komande zapravo zapocinju rad i slazu naslov i apstrakt:

* `\StartPaper` - ova komanda zapocinje rad u jednom stupcu
* `\StartDoublePaper` - ova komanda zapocinje rad u dva stupca

Ukoliko je rad u dva stupca **obavezno je** negde u drugom stupcu prve strane (idealno na pocetku) staviti komandu `\AuthorExHere` kako bi se dobro slozili podaci o autoria i mentorima. (Neophodno zbog tehnickih ogranicenja LaTeX-a). Ukoliko se rad slaze u jednom stupcu, ovu komandu ne koristiti.

Na kraju rada se stavlja komanda `\EndPaper` koja slaze apstrakt na engleskom.

> **Napomena**: kada se slaze tekst u dva stupca, komanda `\clearpage` prelazi na **novu stranu** cak i u prvom stupcu, dok `\newpage` prelazi u sledeci stubac.

## Zamene za LaTeX komande

Sve LaTeX komande mogu da se normalno koriste. Ali, kako bi se odrzala uniformnost, koristiti sledece dodatne komande umesto njihovih ekvivalenata:

* `\Figure{<putanja>}{<opis na srp>}{<opis na eng>}` koristiti umesto `figure` okruzenja. Putanja je relativna putanja do datoteke koju treba ubaciti. Npr:
    ```latex
    \Firuge{slika1.png}{Prikaz toga i toga}{Depiction of so and so}
    ```
* `\FigureDouble{<putanja>}{<opis na srp>}{<opis na eng>}` - isto kao `\Figure`, ali slaze sliku preko cele strane u radovima u dva stupca.
* `\Table{<definicija tablele>}{<opis na srp>}{<opis na eng>}` - isto kao `\Figure`, samo za `table` okruženje.
* `\TableDouble{<definicija tablele>}{<opis na srp>}{<opis na eng>}` - isto kao `\FigureDouble`, samo za `table` okruženje.

Umesto bilo kog bibliografskog alata, izvori se rucno navode. Komanda `\Source{<tekst>}` se stara da poravnjanje bude kako treba.

## Slanje rada putem **Pull Request-a (PR)**

Kada završite rad i proverite da PDF uspešno generiše, sledeći korak je da pošaljete svoj rad organizatorima preko **Pull Request**-a.

Ovo je standardni način saradnje na GitHub-u – vi predlažete izmene (svoj rad), a organizatori ih pregledaju i odobravaju.


### Otvorite repozitorijum

- Ako koristite **GitHub Codespace**, samo otvorite odgovarajući Codespace.
- Ako radite **lokalno**, otvorite repozitorijum u VS Code-u (`File > Open Folder...`).

### Napravite novu granu (branch)

1. U donjem levom uglu kliknite na naziv trenutne grane (npr. `master`)
2. Kliknite na **"Create new branch"**
3. Nazovite granu npr. `rad-ime-prezime-2025` i potvrdite

### Napravite i uredite svoj rad

1. U folderu `2025/` kreirajte novi podfolder sa svojim imenom
2. Dodajte `.tex` fajl, eventualno slike, `.gnu` itd.
3. Pratite stil iz primera (`2020/`)

### Testirajte generisanje PDF-a

1. Otvorite **Terminal**:
   - `Ctrl + `` (backtick)` ili
   - Meni: `Terminal > New Terminal`
2. Pokrenite komandu:

```bash
make
```

1. U folderu bi trebalo da se pojavi vaš `.pdf` fajl

### Sačuvajte promene (Commit)

1. Kliknite na ikonicu **Source Control** (levo, izgleda kao grana)
2. Upišite poruku npr. `Dodavanje rada - Ana Petrović`
3. Kliknite na dugme **Commit**

### Pošaljite granu (Push)

1. Nakon commita, pojaviće se poruka:  
   > "This branch has not been published..."
2. Kliknite na dugme **"Publish Branch"**

### Napravite Pull Request (PR)

1. U gornjem desnom uglu VS Code-a kliknite na **"Create Pull Request"**
   - Ako ne vidite dugme, otvorite repozitorijum na GitHub-u i kliknite na `Compare & pull request`
2. Unesite naslov, npr: `Rad za zbornik – Ana Petrović`
3. Kliknite **"Create pull request"**


Čestitamo! Vaš rad je poslat i biće pregledan od strane organizatora. Nakon odobrenja, postaje deo zvaničnog zbornika.

Sada se mo\ete vratiti na glavnu granu ako želite da počnete sa pisanjem novog rada. Nakon što ste poslali Pull Request i završili rad: 

1. Kliknite u donjem levom uglu na naziv trenutne grane (npr. rad-ime-prezime-2025) 
2. Iz liste izaberite main
3. Kliknite "Switch Branch"

Ako koristite Codespace, sve se automatski ažurira — možete bezbedno obrisati staru granu nakon spajanja (merge).

Slično, ako organizatori imaju primedbe, na granu sa Vašim radom se možete vratiti kroz isti postupak.

# Često postavljana pitanja (FAQ)

## Nikada nisam radio/la u LaTeX-u. Da li mogu da učestvujem?

Apsolutno! U repozitorijumu se nalaze gotovi primeri koje možete kopirati i prilagoditi svom radu. Takođe, radno okruženje vam omogućava da radite bez instalacije dodatnih alata – sve što vam treba je dostupno direktno u internet pregledaču ili kroz Visual Studio Code.

## Mogu li raditi sa Windows / macOS / Linux računara?

Da. Obezbeđene metode (Codespaces ili lokalni razvoj sa VS Code + Docker) rade na svim savremenim operativnim sistemima. Potrebna je stabilna internet konekcija ako koristite Codespaces.

## Kako predajem rad?

Nakon što završite rad i uverite se da PDF uspešno generiše, potrebno je da napravite Pull Request kroz grafički interfejs (VS Code ili GitHub), prema uputstvu u README fajlu. 

## Šta ako mi se PDF ne generiše ili dobijem grešku?

Najčešći uzroci su:

* Greška u LaTeX sintaksi (`\begin` bez odgovarajućeg `\end`, itd.)
* Nedostajuće slike ili plotovi
* Naziv fajla sadrži nedozvoljene karaktere (koristite samo slova, brojeve i donje crte)

Ako ne možete da rešite grešku, slobodno kontaktirajte tehničku podršku.

## Mogu li više osoba raditi zajedno na jednom radu?

Da. Najbolje je da svi koriste istu granu (branch) i komuniciraju jasno oko toga ko kada pravi izmene. GitHub čuva istoriju svih izmena.

## Šta ako ne stignem sve da završim odjednom?

Nema problema. Možete u bilo kom trenutku sačuvati napredak i nastaviti kasnije. Sve izmene ostaju zabeležene, a vaš Codespace ili lokalni repozitorijum čuvaju vaš rad dok ga ne pošaljete.

## Ostalo ...

Ako imate dodatna pitanja, slobodno ih postavite organizatorima – tu smo da pomognemo!

