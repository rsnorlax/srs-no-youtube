# srs-no-youtube

Сборка своих `sing-box` ruleset-файлов для Podkop:

- `ru-domains-no-youtube.srs`
- `ru-ips-merged.srs`

Смысл простой:

- берём несколько внешних `.srs`-источников;
- объединяем домены и IP/CIDR;
- вырезаем YouTube-связанные домены;
- публикуем готовые файлы в `dist/`;
- Podkop забирает уже готовые `.srs` по HTTPS с GitHub.

---

## Что лежит в `dist/`

После сборки workflow создаёт и коммитит:

- `dist/ru-domains-no-youtube.srs`
- `dist/ru-domains-no-youtube.json`
- `dist/ru-domains-no-youtube.lst`
- `dist/ru-ips-merged.srs`
- `dist/ru-ips-merged.json`
- `dist/ru-ips-merged.lst`
- `dist/ru-rules-build-meta.json`
- `dist/SHA256SUMS`

Основные файлы для Podkop:

- `https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-domains-no-youtube.srs`
- `https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-ips-merged.srs`

Если у тебя ветка не `main`, поменяй URL.

---

## Как это работает

GitHub Actions:

- запускается вручную через **Run workflow**;
- запускается по расписанию каждый день;
- ставит `sing-box`;
- запускает `build_podkop_rules.py`;
- складывает результат в `dist/`;
- коммитит изменения обратно в репозиторий.

---

## Структура репозитория

```text
.
├── .github/
│   └── workflows/
│       └── build.yml
├── build_podkop_rules.py
├── README.md
└── dist/
```

`dist/` можно не создавать вручную — workflow создаст сам.

---

## Что нужно сделать один раз на GitHub

### 1. Залить файлы в репозиторий

Положи в репу:

- `build_podkop_rules.py`
- `README.md`
- `.github/workflows/build.yml`

### 2. Включить GitHub Actions

Открой репозиторий:

- **Settings** → **Actions** → **General**

Проверь:

- Actions не выключены;
- внизу в **Workflow permissions** стоит **Read and write permissions**;
- галочка **Allow GitHub Actions to create and approve pull requests** не нужна.

### 3. Проверить ветку

В этом README и workflow по умолчанию используется ветка `main`.
Если у тебя ветка называется `master`, надо заменить `main`:

- в URL из README;
- при необходимости в своих ссылках.

---

## Первый запуск

1. Залей файлы в репу.
2. Открой **Actions**.
3. Выбери workflow **Build Podkop Rules**.
4. Нажми **Run workflow**.
5. Дождись зелёного статуса.
6. Проверь, что в репе появилась папка `dist/` с файлами.

---

## Ссылки для Podkop

### Внешний список доменов

```text
https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-domains-no-youtube.srs
```

### Внешний список подсетей

```text
https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-ips-merged.srs
```

Их уже можно вставлять в Podkop через веб-морду.

---

## Как быстро проверить, что GitHub реально отдаёт файл

На OpenWrt:

```bash
URL='https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-domains-no-youtube.srs'

rm -f /tmp/ru-domains-no-youtube.srs
uclient-fetch -O /tmp/ru-domains-no-youtube.srs "$URL"

ls -lh /tmp/ru-domains-no-youtube.srs
```

Для IP:

```bash
URL='https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-ips-merged.srs'

rm -f /tmp/ru-ips-merged.srs
uclient-fetch -O /tmp/ru-ips-merged.srs "$URL"

ls -lh /tmp/ru-ips-merged.srs
```

---

## Ручной IP exclude

Если надо вырезать какие-то CIDR руками, используй файл:

```text
dist/youtube_ip_exclude.txt
```

Формат:

```text
1.2.3.0/24
5.6.7.8/32
```

Комментарии с `#` поддерживаются.

Если файл отсутствует, скрипт создаст шаблон автоматически.

---

## Локальный запуск у себя

Если хочешь гонять сборку не только в GitHub Actions:

```bash
curl -fsSL https://sing-box.app/install.sh | sh
python3 build_podkop_rules.py
```

Или задать свою папку вывода:

```bash
OUT_DIR=/tmp/podkop-dist python3 build_podkop_rules.py
```

---

## Если workflow не пушит изменения

Смотри по порядку:

1. В репозитории включены **Actions**.
2. В **Workflow permissions** выставлено **Read and write**.
3. Нет branch protection, который запрещает боту писать в `main`.
4. Workflow реально отработал без ошибки на шаге `Commit and push dist`.

---

## Если Podkop не скачивает

Проверяй отдельно с OpenWrt:

```bash
uclient-fetch -O /tmp/test.srs 'https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-domains-no-youtube.srs'
```

Если файл качается руками, значит дальше вопрос уже к Podkop UI, а не к GitHub.

---

## Почему этот вариант лучше

- не нужен Nextcloud;
- не нужен домен для локальной сети;
- не нужен self-hosted HTTP;
- не нужны токены в URL;
- GitHub даёт стабильный HTTPS URL;
- Podkop видит обычную ссылку на `.srs`.
