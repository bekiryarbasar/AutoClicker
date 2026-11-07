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
- İlk video seçiminde yaklaşık 39 MB'lık video bileşeni için bir defa onay istenir; indirilip bilgisayarda saklanır. Video 510×680 çözünürlüğe, saniyede 8 kareye ve düşük bit hızına dönüştürülür. Yalnızca seçilen yerel dosya kullanılır; oynarken internet verisi harcanmaz.
- Açılışta GitHub Releases sürümü kontrol edilir. Güncelleme varsa kullanıcıya sorulur.
- Onaydan sonra yeni `AutoClicker.exe` indirilir, SHA-256 özeti doğrulanır, uygulama kendini değiştirip yeniden başlatır. Kurulum başarısız olursa önceki EXE yedekten geri yüklenir.
- İnternet yoksa veya GitHub'a ulaşılamazsa uygulama normal şekilde açılır.

## İndirme ve kullanma

1. [Son sürüm sayfasını açın](https://github.com/bekiryarbasar/AutoClicker/releases/latest).
2. `AutoClicker.exe` dosyasını indirin. Windows uyarı verirse yalnızca dosyayı GitHub'daki bu resmi sürüm sayfasından indirdiğinizi doğruladıktan sonra çalıştırın.
3. İndirilen EXE'ye çift tıklayın. Kurulum veya ek dosya gerekmez.
4. Güncelleme bulunduğunda **Evet** derseniz indirip kurar ve yeniden açar; **Hayır** mevcut sürümle devam eder.

## Kullanım

Sol ve sağ paneldeki kaydırıcılarla hızı ayarlayın. Tetikleyiciyi değiştirmek için ilgili **TETİK** alanına tıklayıp klavyede bir tuşa veya fare düğmesine basın. **BASILI TUT** veya **AÇ/KAPAT** modunu seçin. Fotoğraf veya video arka planını sağ üstteki klasör simgesinden değiştirebilirsiniz. Video hazırlığı arka planda sürerken uygulamayı kullanmaya devam edebilirsiniz.

## Ayarlar ve dosyalar

Kullanıcı ayarları `%APPDATA%\AutoClicker2` altında tutulur. Güncelleme yalnızca uygulamanın EXE dosyasını değiştirir; ayarlar ve seçilen arka plan bu klasörde kaldığından korunur. Kullanıcıya dağıtılan/yayımlanan ana dosya yalnızca `AutoClicker.exe`'dir.

Video arka planı uygulamanın bu klasördeki yerel önbelleğinde tutulur. Video çözücüsü ilk video seçiminde indirilir ve sonraki kullanımlar için aynı klasörde saklanır. Ses çıkarılır; video 8 FPS ve 280 kbit/sn hedef bit hızıyla, pencere boyutuna küçültülerek saklanır. Uygulama video kaynağını internetten indirmez veya bir sunucuya göndermez.

## Yeni sürüm yayımlama

Gerekli ortam: Windows ve Python 3.12. Proje klasöründe PowerShell açın:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`AutoClicker.py` içindeki `APP_VERSION` değerini artırın (ör. `1.0.6`), GitHub'a kaynak değişikliklerini gönderin ve derleyin:

```powershell
git add .
git commit -m "Release v1.0.6"
git push origin main
.\build_release.ps1 -Tag v1.0.6
```

GitHub'da **Releases → Draft a new release** seçin, etiket olarak `v1.0.6` yazın. `release\v1.0.6` içindeki `AutoClicker.exe` ve `AutoClicker-VideoRuntime.zip` dosyalarını ekleyin. Eski v1.0.0 uygulamalarının güncelleyicisini desteklemek için önceki sürümdeki `AutoClicker-Windows.zip` ve ona ait `SHA256SUMS.txt` dosyalarını da yeni sürüme ekleyin. Üçüncü taraf lisansları `THIRD_PARTY_NOTICES.md` içinde listelenir.

Güncelleyici en son kararlı sürümü kontrol eder ve indirilen EXE'nin GitHub SHA-256 özetini doğrular.

## Proje yapısı

- `AutoClicker.py`: uygulama arayüzü, tıklama motoru ve sürüm numarası.
- `updater.py`: açılışta sürüm kontrolü, kullanıcı onayı, indirme doğrulaması, kendini güncelleme ve geri alma.
- `AutoClicker.spec`, `tk_runtime_hook.py`, `hooks/`, `tk-data/`: PyInstaller ve Tcl/Tk paketleme ayarları.
- `build_release.ps1`: yalnızca dağıtılacak tek EXE'yi oluşturur.
- `THIRD_PARTY_NOTICES.md`: FFmpeg ve Pillow lisans/kaynak bildirimleri.
