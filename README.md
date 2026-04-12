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



## Ссылки для Podkop

### Внешний список доменов

```text
https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-domains-no-youtube.srs
```

### Внешний список подсетей

```text
https://raw.githubusercontent.com/rsnorlax/srs-no-youtube/main/dist/ru-ips-merged.srs
```
