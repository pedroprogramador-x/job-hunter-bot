"""Configuração e matching da watchlist estratégica de empresas."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

CompanyCategory = Literal["remote", "maceio"]
CompanyPriority = Literal["very_high", "high", "medium"]

WATCHLIST_BONUSES: dict[CompanyPriority, int] = {
    "very_high": 3,
    "high": 2,
    "medium": 1,
}


@dataclass(frozen=True)
class CompanyWatchlistEntry:
    canonical_name: str
    aliases: tuple[str, ...]
    category: CompanyCategory
    priority: CompanyPriority
    active: bool = True


@dataclass(frozen=True)
class TargetCompanyMatch:
    canonical_name: str
    priority: CompanyPriority
    category: CompanyCategory
    bonus: int


COMPANY_WATCHLIST: tuple[CompanyWatchlistEntry, ...] = (
    CompanyWatchlistEntry("Nomus", ("nomus",), "remote", "very_high"),
    CompanyWatchlistEntry(
        "It4us Cyber Security",
        ("it4us", "it4us cyber security", "#vemprait4us", "vemprait4us"),
        "remote",
        "very_high",
    ),
    CompanyWatchlistEntry("Luby", ("luby",), "remote", "very_high"),
    CompanyWatchlistEntry(
        "BairesDev", ("bairesdev", "baires dev"), "remote", "very_high"
    ),
    CompanyWatchlistEntry(
        "Magalu Cloud",
        ("magalu cloud", "magazine luiza", "luizalabs", "luiza labs"),
        "remote",
        "very_high",
    ),
    CompanyWatchlistEntry("Gupy", ("gupy",), "remote", "high"),
    CompanyWatchlistEntry(
        "Nuvemshop",
        ("nuvemshop", "tienda nube", "tiendanube"),
        "remote",
        "high",
    ),
    CompanyWatchlistEntry("Asaas", ("asaas",), "remote", "high"),
    CompanyWatchlistEntry(
        "Zup Innovation", ("zup innovation", "zup"), "remote", "high"
    ),
    CompanyWatchlistEntry(
        "South System", ("south system",), "remote", "high"
    ),
    CompanyWatchlistEntry("Cadastra", ("cadastra",), "remote", "high"),
    CompanyWatchlistEntry(
        "Wave by Bemobi", ("wave by bemobi", "bemobi"), "remote", "high"
    ),
    CompanyWatchlistEntry(
        "CapLink", ("caplink", "cap link"), "remote", "high"
    ),
    CompanyWatchlistEntry(
        "Clicksign", ("clicksign", "click sign"), "remote", "high"
    ),
    CompanyWatchlistEntry("Invillia", ("invillia",), "remote", "high"),
    CompanyWatchlistEntry("Radix", ("radix",), "remote", "high"),
    CompanyWatchlistEntry("Inmetrics", ("inmetrics",), "remote", "high"),
    CompanyWatchlistEntry(
        "CI&T", ("ci&t", "ci and t", "ciandt"), "remote", "high"
    ),
    CompanyWatchlistEntry(
        "Voltz / Energisa", ("voltz", "energisa"), "remote", "high"
    ),
    CompanyWatchlistEntry("Kryptus", ("kryptus",), "remote", "high"),
    CompanyWatchlistEntry(
        "Asa Branca", ("asa branca",), "maceio", "very_high"
    ),
    CompanyWatchlistEntry("Trakto", ("trakto",), "maceio", "very_high"),
    CompanyWatchlistEntry(
        "Hand Talk by Sorenson",
        ("hand talk", "hand talk by sorenson", "sorenson"),
        "maceio",
        "very_high",
    ),
    CompanyWatchlistEntry(
        "Roga Labs", ("roga labs",), "maceio", "very_high"
    ),
    CompanyWatchlistEntry("Stant", ("stant",), "maceio", "high"),
    CompanyWatchlistEntry(
        "Grupo Equatorial",
        ("grupo equatorial", "equatorial energia"),
        "maceio",
        "high",
    ),
    CompanyWatchlistEntry(
        "Unimed Maceió", ("unimed maceio",), "maceio", "high"
    ),
    CompanyWatchlistEntry(
        "Grupo JRCA", ("grupo jrca", "jrca"), "maceio", "high"
    ),
    CompanyWatchlistEntry(
        "TechCraft Brazil",
        ("techcraft brazil", "techcraft"),
        "maceio",
        "high",
    ),
    CompanyWatchlistEntry(
        "SoftwareS Automação Comercial",
        ("softwares automacao comercial",),
        "maceio",
        "medium",
    ),
)


def normalize_company_name(value: object) -> str:
    """Normaliza apenas diferenças seguras de grafia, sem fuzzy matching."""
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_alias_index() -> tuple[tuple[str, CompanyWatchlistEntry], ...]:
    aliases = (
        (normalize_company_name(alias), entry)
        for entry in COMPANY_WATCHLIST
        if entry.active
        for alias in entry.aliases
    )
    return tuple(sorted(aliases, key=lambda item: len(item[0]), reverse=True))


_ALIAS_INDEX = _build_alias_index()


def match_target_company(company_name: object) -> TargetCompanyMatch | None:
    """Retorna um match explícito da watchlist ou ``None``.

    Aliases podem aparecer acompanhados de sufixos societários ou de marca, mas
    precisam coincidir em limites de palavras. Isso mantém o matching tolerante
    a nomes como "Magazine Luiza S.A." sem recorrer a fuzzy matching agressivo.
    """
    normalized_name = normalize_company_name(company_name)
    if not normalized_name:
        return None

    padded_name = f" {normalized_name} "
    for normalized_alias, entry in _ALIAS_INDEX:
        if f" {normalized_alias} " in padded_name:
            return TargetCompanyMatch(
                canonical_name=entry.canonical_name,
                priority=entry.priority,
                category=entry.category,
                bonus=WATCHLIST_BONUSES[entry.priority],
            )
    return None
