# GTA clipper (rulează pe GitHub, fără laptop)

La fiecare 3 ore, GitHub Actions face clipuri verticale noi din stream-urile GTA ale lui **Lacy** și **Kai Cenat**, le verifică și le urcă în Google Drive. Tu doar le postezi.

## Ce face o rundă

1. Pentru fiecare streamer din `ci/streamers.json` caută cel mai nou stream cu „GTA” în titlu pe Twitch.
2. Face clipuri doar din orele noi față de runda trecută, cel mult 6 ore de stream pe rundă: 5 clipuri pe streamer, de 20–35 de secunde, care încep direct cu momentul principal, fără înjurături (mascate în subtitrări și mute în sunet) și cu numele streamerului și hashtagul în titlu.
3. Verifică fiecare clip (lungime, liniște, înjurături, logo-uri, fața streamerului) și îl pune în **Ready** sau **Rejected**.
4. Urcă rezultatul în Google Drive, în `GTA-Clips/<data_ora>/`: folderele `Ready/` și `Rejected/`, plus `REPORT.md` și `POSTS.txt`, cu titlul și descrierea fiecărui clip, gata de copiat.
5. Salvează progresul în `state/`, ca runda următoare să continue de unde a rămas.

Dacă se termină limita abonamentului Claude, runda se oprește, iar aceleași ore se reiau la runda următoare. Nimic nu se postează automat.

## Configurare (o singură dată)

### 1. Tokenul Claude (abonamentul tău)
În PowerShell, pe laptop:
```powershell
& "$HOME\.local\bin\claude.exe" setup-token
```
Se deschide browserul: autorizezi, apoi copiezi tokenul afișat. Pe GitHub, intră în repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:
- Name: `CLAUDE_CODE_OAUTH_TOKEN`
- Secret: tokenul copiat

Nu pune tokenul în niciun fișier și nu-l trimite nimănui. Tokenul expiră după aproximativ un an; atunci repeți pasul.

### 2. Google Drive
În PowerShell:
```powershell
winget install Rclone.Rclone
```
Deschide o fereastră **nouă** de PowerShell, apoi:
```powershell
rclone config create gdrive drive scope drive.file
```
Se deschide browserul: alegi contul Google și permiți accesul. Cu `drive.file`, rclone vede doar fișierele create de el, nu tot Drive-ul tău. Apoi afișează configurația:
```powershell
Get-Content (rclone config file | Select-Object -Last 1)
```
Copiezi tot textul afișat (de la `[gdrive]` până la sfârșit) într-un secret nou pe GitHub:
- Name: `RCLONE_CONFIG`
- Secret: textul copiat

Fără acest secret, clipurile se pot descărca 7 zile din pagina rundei de pe GitHub (Actions → runda → Artifacts).

### 3. Pornire
Repo → **Actions** → **GTA clips** → **Run workflow**. După aceea pornește singur la fiecare 3 ore.

## Oprire
Repo → **Actions** → **GTA clips** → meniul „...” → **Disable workflow**.

## Modificări
- Streameri, număr de clipuri, ore pe rundă: `ci/streamers.json`
- `game_max_x: 0.70` taie chat-ul din dreapta la Lacy; pentru alt streamer cu chat în dreapta, pune aceeași valoare.
- Nu rula în paralel și programarea de pe laptop (`clip-streamers.ps1`), altfel apar clipuri duble.
