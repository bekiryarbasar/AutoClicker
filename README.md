# AutoClicker

Windows için Türkçe arayüzlü, sol ve sağ fare tıklamalarını ayrı ayrı yönetebileceğiniz otomatik tıklama uygulaması.

## Özellikler

- Sol ve sağ tıklama bağımsız çalışır ve aynı anda kullanılabilir.
- Her taraf için saniyede 1–60 tıklama (CPS) hızı seçilebilir.
- Klavye veya fare tetikleyicileri ayrı ayrı atanabilir; varsayılanlar sol için `F6`, sağ için `F7`.
- **Basılı tut** ve **aç/kapat** çalışma biçimleri bulunur.
- İsteğe bağlı değişken hız, seçilen hızın en fazla 3 CPS altına iner.
- Canlı sol/sağ CPS göstergesi vardır.
- Uygulamanın sürüm numarası arayüzün sağ alt köşesinde görünür.
- PNG, JPG/JPEG, BMP, GIF veya WebP kişisel arka plan olarak seçilebilir.
- MP4, MOV, M4V, AVI, MKV veya WebM video arka plan olarak seçilebilir; video sessiz ve döngü halinde oynatılır.
- Video desteği uygulamanın içine dahildir; ek bir dosya indirmek gerekmez. Video sessizce döngü halinde oynatılır ve bilgisayarda yerel olarak saklanır.
- Açılışta GitHub Releases sürümü kontrol edilir. Güncelleme varsa kullanıcıya sorulur.
- Onaydan sonra yeni `AutoClicker.exe` indirilir, SHA-256 özeti doğrulanır, uygulama kendini değiştirip yeniden başlatır. Kurulum başarısız olursa önceki EXE yedekten geri yüklenir.
- İnternet yoksa veya GitHub'a ulaşılamazsa uygulama normal şekilde açılır.

## İndirme ve kullanma

1. [Son sürüm sayfasını açın](https://github.com/bekiryarbasar/AutoClicker/releases/latest).
2. Varlıklar bölümünden yalnızca `AutoClicker.exe` dosyasını indirin. Windows uyarı verirse dosyayı resmi GitHub sürüm sayfasından indirdiğinizi doğrulayın.
3. İndirilen EXE'ye çift tıklayın. Kurulum veya ek dosya gerekmez.
4. Güncelleme bulunduğunda **Evet** derseniz indirip kurar ve yeniden açar; **Hayır** mevcut sürümle devam eder.

## Kullanım

Sol ve sağ paneldeki kaydırıcılarla hızı ayarlayın. Tetikleyiciyi değiştirmek için ilgili **TETİK** alanına tıklayıp klavyede bir tuşa veya fare düğmesine basın. **BASILI TUT** veya **AÇ/KAPAT** modunu seçin. Fotoğraf veya video arka planını sağ üstteki klasör simgesinden değiştirebilirsiniz. Video hazırlığı arka planda sürerken uygulamayı kullanmaya devam edebilirsiniz.

## Ayarlar ve dosyalar

Kullanıcı ayarları `%APPDATA%\AutoClicker2` altında tutulur. Güncelleme yalnızca uygulamanın EXE dosyasını değiştirir; ayarlar ve seçilen arka plan bu klasörde kaldığından korunur. Kullanıcıya dağıtılan/yayımlanan ana dosya yalnızca `AutoClicker.exe`'dir.

Video arka planı `%APPDATA%\AutoClicker2` klasöründe tutulur. Ses çıkarılır; video 30 FPS'te ve 510×680 çözünürlükte saklanır. Pencere küçültülür veya başka bir pencere AutoClicker'ın üstünü kapatırsa oynatma duraklar; masaüstüne tıklamak videoyu durdurmaz. Pencere yeniden görünür olduğunda video kaldığı yerden sürer. Uygulama video kaynağını internetten indirmez veya bir sunucuya göndermez.

## Yeni sürüm yayımlama

Gerekli ortam: Windows ve Python 3.12. Proje klasöründe PowerShell açın:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`AutoClicker.py` içindeki `APP_VERSION` değerini artırın (ör. `1.0.12`), kaynak değişikliklerini gönderin ve derleyin:

```powershell
git add AutoClicker.py AutoClicker.spec build_release.ps1 README.md RELEASE_NOTES_v1.0.12.md
git commit -m "Release v1.0.12"
git push origin main
.\build_release.ps1 -Tag v1.0.12
```

GitHub'da **Releases → Draft a new release** seçin, etiketi sürümle eşleştirin ve sürüm notlarını ekleyin. `release\<etiket>` içinden yalnızca `AutoClicker.exe` dosyasını varlık olarak yükleyin. Video desteği EXE'ye dahildir. GitHub ayrıca kaynak kodu arşivlerini otomatik oluşturur.

Güncelleyici en son kararlı sürümü kontrol eder ve indirilen EXE'nin GitHub SHA-256 özetini doğrular.

## Proje yapısı

- `AutoClicker.py`: uygulama arayüzü, tıklama motoru ve sürüm numarası.
- `updater.py`: açılışta sürüm kontrolü, kullanıcı onayı, indirme doğrulaması, kendini güncelleme ve geri alma.
- `AutoClicker.spec`, `tk_runtime_hook.py`, `hooks/`, `tk-data/`: PyInstaller ve Tcl/Tk paketleme ayarları.
- `build_release.ps1`: yalnızca dağıtılacak tek EXE'yi oluşturur.
- `THIRD_PARTY_NOTICES.md`: FFmpeg ve Pillow lisans/kaynak bildirimleri.
