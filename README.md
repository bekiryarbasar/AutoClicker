# AutoClicker

Windows için Türkçe arayüzlü, sol ve sağ fare tıklamalarını ayrı ayrı ayarlayabileceğiniz hafif bir otomatik tıklama uygulaması.

## Özellikler

- **Bağımsız sol ve sağ tıklama:** İki düğme aynı anda çalışabilir; her biri ayrı hız ve tetikleyici kullanır.
- **Ayarlanabilir tıklama hızı:** Her düğme için saniyede 1–60 tıklama (CPS) seçilebilir.
- **Değiştirilebilir tetikleyiciler:** Sol ve sağ tıklama için ayrı klavye tuşu veya fare düğmesi atanabilir. Varsayılan klavye kısayolları sol için `F6`, sağ için `F7`.
- **İki çalışma biçimi:** Tetikleyiciyi basılı tuttuğunuz sürece tıklama veya bir kez basarak başlatıp tekrar basarak durdurma.
- **Değişken hız:** İsteğe bağlı olarak hız, seçilen CPS değerinden en fazla 3 CPS aşağıda değişir; alt sınır 1 CPS'tir.
- **Canlı durum ve sayaç:** Uygulama tıklamanın çalışıp çalışmadığını ve sol/sağ için ölçülen anlık CPS değerlerini gösterir.
- **Kişisel arka plan:** PNG, JPG/JPEG, BMP, GIF veya WebP görseli seçilebilir. Seçilen arka plan kullanıcı klasöründe saklanır.
- **GitHub Releases güncellemeleri:** Açılışta yeni kararlı sürüm aranır. Yeni sürüm bulunursa indirme ve yeniden başlatma kullanıcı onayıyla başlar.
- **Doğrulamalı ve geri alınabilir kurulum:** ZIP SHA-256 ile doğrulanır; program ve güncelleme yardımcısı değiştirilmeden önce yedeklenir. Yeni sürüm başlangıç onayını vermezse eski dosyalar geri yüklenir.

## Kullanım

1. `AutoClicker.exe` dosyasını `AutoClickerUpdater.exe` ve `updater_config.json` ile aynı klasöre çıkarıp çalıştırın.
2. Sol ve sağ paneldeki kaydırıcılarla CPS değerlerini ayarlayın.
3. Bir tetikleyiciyi değiştirmek için ilgili **TETİK** alanına tıklayın, ardından istediğiniz klavye tuşuna veya fare düğmesine basın.
4. **BASILI TUT** ya da **AÇ/KAPAT** çalışma biçimini seçin.
5. Tıklamayı ilgili tetikleyiciyle başlatın. Arka planı değiştirmek için sağ üstteki klasör simgesini kullanın.

## Kullanıcı dosyaları

Ayar dosyası ve seçilen arka plan `%APPDATA%\AutoClicker2` altında tutulur. Güncelleyici bu klasöre dokunmaz; yalnızca `AutoClicker.exe` ve `AutoClickerUpdater.exe` dosyalarını değiştirir. Arka plan seçimi saklanır. CPS, tetikleyici, rastgele hız ve çalışma biçimi mevcut uygulama sürümünde her açılışta varsayılan değerlerden başlar.

## İndirme ve ilk kurulum

GitHub Releases sayfasındaki `AutoClicker-Windows.zip` dosyasını indirin ve içindeki üç dosyayı aynı klasöre çıkarın. İlk güncelleme destekli sürüme geçerken eski EXE'yi kapatıp yeni paketi bir kez elle kurmanız gerekir; güncelleme kodu eski EXE'de bulunmaz. Kullanıcı ayarları `%APPDATA%` altında kaldığından korunur.

## Güncelleme deposu

Güncelleyici `updater_config.json` içindeki `owner` ve `repo` değerleriyle herkese açık GitHub deposunu arar. Bu projede depo `bekiryarbasar/AutoClicker` olarak ayarlanmıştır. Gizli depolar ve erişim anahtarları kullanılmaz.

Her kararlı GitHub Release şu iki varlığı içermelidir:

- `AutoClicker-Windows.zip` — kökünde `AutoClicker.exe`, `AutoClickerUpdater.exe` ve `updater_config.json` bulunan paket.
- `SHA256SUMS.txt` — ZIP dosyasının SHA-256 özeti.

Güncelleyici `v1.0.0` gibi sayısal sürüm etiketlerini karşılaştırır; taslakları ve ön sürümleri atlar.

## Kaynaktan derleme

Windows ve Python 3.12 gerekir. PowerShell'i proje klasöründe açın:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\build_release.ps1 -Tag v1.0.0
```

Betik `AutoClicker.spec` ve `AutoClickerUpdater.spec` ile iki tek dosyalı Windows EXE üretir, ardından Release ZIP'i ve SHA-256 dosyasını hazırlar. Yeni sürüm yayımlarken `AutoClicker.py` içindeki `APP_VERSION` değerini artırıp aynı etiketi kullanın; örneğin `APP_VERSION = "1.0.1"` ve `-Tag v1.0.1`.

## Depo yapısı

- `AutoClicker.py` — arayüz ve tıklama motoru.
- `updater.py` — GitHub Release kontrolü, ZIP doğrulaması ve güncelleme başlatma.
- `AutoClickerUpdater.py` — yedekleme, dosya değiştirme, açılış doğrulaması ve geri alma.
- `*.spec`, `tk_runtime_hook.py`, `hooks/`, `tk-data/` — PyInstaller ve Tcl/Tk paketleme ayarları.
- `updater_config.json` — GitHub depo adı ve güncelleme seçeneği.
