# AutoClicker

Windows için Türkçe arayüzlü, sol ve sağ fare tıklamalarını ayrı ayrı yönetebileceğiniz otomatik tıklama uygulaması.

## Özellikler

- Sol ve sağ tıklama bağımsız çalışır ve aynı anda kullanılabilir.
- Her taraf için saniyede 1–60 tıklama (CPS) hızı seçilebilir.
- Klavye veya fare tetikleyicileri ayrı ayrı atanabilir; varsayılanlar sol için `F6`, sağ için `F7`.
- **Basılı tut** ve **aç/kapat** çalışma biçimleri bulunur.
- İsteğe bağlı değişken hız, seçilen hızın en fazla 3 CPS altına iner.
- Canlı sol/sağ CPS göstergesi vardır.
- PNG, JPG/JPEG, BMP, GIF veya WebP kişisel arka plan olarak seçilebilir.
- Açılışta GitHub Releases sürümü kontrol edilir. Güncelleme varsa kullanıcıya sorulur.
- Onaydan sonra yeni `AutoClicker.exe` indirilir, SHA-256 özeti doğrulanır, uygulama kendini değiştirip yeniden başlatır. Kurulum başarısız olursa önceki EXE yedekten geri yüklenir.
- İnternet yoksa veya GitHub'a ulaşılamazsa uygulama normal şekilde açılır.

## İndirme ve kullanma

1. [Son sürüm sayfasını açın](https://github.com/bekiryarbasar/AutoClicker/releases/latest).
2. `AutoClicker.exe` dosyasını indirin. Windows uyarı verirse yalnızca dosyayı GitHub'daki bu resmi sürüm sayfasından indirdiğinizi doğruladıktan sonra çalıştırın.
3. İndirilen EXE'ye çift tıklayın. Kurulum veya ek dosya gerekmez.
4. Güncelleme bulunduğunda **Evet** derseniz indirip kurar ve yeniden açar; **Hayır** mevcut sürümle devam eder.

## Kullanım

Sol ve sağ paneldeki kaydırıcılarla hızı ayarlayın. Tetikleyiciyi değiştirmek için ilgili **TETİK** alanına tıklayıp klavyede bir tuşa veya fare düğmesine basın. **BASILI TUT** veya **AÇ/KAPAT** modunu seçin. Arka planı sağ üstteki klasör simgesinden değiştirebilirsiniz.

## Ayarlar ve dosyalar

Kullanıcı ayarları `%APPDATA%\AutoClicker2` altında tutulur. Güncelleme yalnızca uygulamanın EXE dosyasını değiştirir; ayarlar ve seçilen arka plan bu klasörde kaldığından korunur. Kullanıcıya dağıtılan/yayımlanan ana dosya yalnızca `AutoClicker.exe`'dir.

## Yeni sürüm yayımlama

Gerekli ortam: Windows ve Python 3.12. Proje klasöründe PowerShell açın:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`AutoClicker.py` içindeki `APP_VERSION` değerini artırın (ör. `1.0.2`), GitHub'a kaynak değişikliklerini gönderin ve derleyin:

```powershell
git add .
git commit -m "Release v1.0.2"
git push origin main
.\build_release.ps1 -Tag v1.0.2
```

GitHub'da **Releases → Draft a new release** seçin, etiket olarak `v1.0.2` yazın, betiğin ürettiği `release\v1.0.2\AutoClicker.exe` dosyasını ekleyin ve yayına alın. Güncelleyici yalnızca bu herkese açık deponun en son kararlı sürümünü kabul eder. API'deki GitHub SHA-256 özeti dosya bütünlüğünü doğrular.

## Proje yapısı

- `AutoClicker.py`: uygulama arayüzü, tıklama motoru ve sürüm numarası.
- `updater.py`: açılışta sürüm kontrolü, kullanıcı onayı, indirme doğrulaması, kendini güncelleme ve geri alma.
- `AutoClicker.spec`, `tk_runtime_hook.py`, `hooks/`, `tk-data/`: PyInstaller ve Tcl/Tk paketleme ayarları.
- `build_release.ps1`: yalnızca dağıtılacak tek EXE'yi oluşturur.
