from urllib.parse import quote

from ..cached_get import cached_get
from ..models import DictionarySource, LookupResult, SourceOptions


class GoogleTranslateSource(DictionarySource):
    FALLBACK_INSTANCES: tuple[str, ...] = (
        "https://lingva.ml",
        "https://translate.astian.org",
    )

    def __init__(self, langcode: str, options: SourceOptions, gtrans_api: str, gtrans_to_langcode: str) -> None:
        super().__init__("Google Translate", langcode, options)
        self.langcode = langcode
        self.to_langcode = gtrans_to_langcode
        self._api_source_langcode = self._normalize_langcode(langcode)
        self._api_target_langcode = self._normalize_langcode(gtrans_to_langcode)
        self._api_endpoints: list[str] = []
        for candidate in (gtrans_api, *self.FALLBACK_INSTANCES):
            normalized = candidate.rstrip("/") if candidate else ""
            if normalized and normalized not in self._api_endpoints:
                self._api_endpoints.append(normalized)
        if not self._api_endpoints:
            raise ValueError("No Google Translate API endpoints configured")
        # Preserve the initially configured endpoint for UI/config dialogs
        self.gtrans_api = self._api_endpoints[0]

    def _lookup(self, word: str) -> LookupResult:
        encoded_word = quote(word, safe="")
        last_error: str | None = None
        for idx, endpoint in enumerate(list(self._api_endpoints)):
            url = f"{endpoint}/api/v1/{self._api_source_langcode}/{self._api_target_langcode}/{encoded_word}"
            try:
                res = cached_get(url)
                data = res.json()
            except Exception as exc:
                last_error = repr(exc)
                continue

            translation = data.get("translation") if isinstance(data, dict) else None
            if isinstance(translation, list):
                translation = "\n".join(str(part) for part in translation if part)
            if translation:
                if idx != 0:
                    self._api_endpoints.insert(0, self._api_endpoints.pop(idx))
                self.gtrans_api = endpoint
                return LookupResult(definition=str(translation))
            last_error = f"Unexpected response from {endpoint}: {data!r}"

        return LookupResult(error=last_error or "Unable to fetch translation from configured endpoints.")

    @staticmethod
    def _normalize_langcode(langcode: str) -> str:
        return "iw" if langcode == "he" else langcode
