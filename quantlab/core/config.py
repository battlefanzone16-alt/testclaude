"""Configuration du système Kalman v6.

Chaque champ est un choix explicite. Les champs marqués STRUCTUREL ne sont pas
destinés à être optimisés (ce sont des règles, pas des curseurs) ; les champs
marqués LIBRE sont ceux que le walk-forward a le droit de balayer. Cette
séparation est ce qui garde le nombre d'essais — et donc la barre du Deflated
Sharpe — sous contrôle.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Config:
    # --- INDICATEURS (STRUCTUREL : répliqué de TradingView, on n'y touche pas) ---
    kalman_pn: float = 0.001
    kalman_mn: float = 1.0
    pvt_left: int = 2
    pvt_right: int = 4

    # --- LIBRE : balayé en walk-forward ---
    dc_length: int = 20

    # --- SIGNAL D'ENTREE (STRUCTUREL) ---
    # "kalman_cross"      : croisement close/Kalman (= EMA-63). Un EVENEMENT :
    #                       se déclenche à chaque oscillation autour de la ligne.
    # "donchian_breakout" : cassure du plus-haut/plus-bas Donchian. Un ETAT :
    #                       le prix doit battre tout le passé récent.
    entry_mode: str = "donchian_breakout"

    # --- DIRECTION (STRUCTUREL) ---
    enable_long: bool = True
    enable_short: bool = True          # v5 tournait long-only ; le CSV montre la parité

    # --- LE FIX v6 (STRUCTUREL, binaire) ---
    # N'entrer que si le prix est DEJA du bon côté de la médiane Donchian.
    # Supprime à la source la population "clôt<Kalman" (778 trades, 0% WR).
    entry_above_median: bool = True

    # --- SORTIE ---
    # Avec entry_above_median, la position démarre en phase médiane : le trailing
    # par la médiane est le seul soft stop nécessaire.
    exit_on_median: bool = True
    exit_on_kalman: bool = False       # soft stop Kalman (la jambe perdante de v5)

    # --- STOP DUR (STRUCTUREL) ---
    sl_mode: str = "wick"              # "wick" = low/high de la bougie de cassure, "atr", "donchian"
    sl_atr_mult: float = 2.0           # LIBRE si sl_mode="atr"
    atr_length: int = 14

    # --- TIME STOP (LIBRE, un seul paramètre) ---
    time_stop_bars: int | None = None  # sortie forcée après N bougies H4 sans résolution

    # --- FILTRES DE QUALITE D'ENTREE (LIBRE) ---
    max_sl_dist: float | None = 0.12   # skip si le SL dur est à plus de 12% (trade illisible)
    max_dist_kalman: float | None = None  # skip si la bougie clôture trop loin du Kalman

    # --- RISQUE (STRUCTUREL) ---
    risk_pct: float = 0.01             # 1% du capital par trade sur le SL dur
    max_lev: float = 3.0               # cap de levier par position
    max_gross: float = 3.0             # cap d'exposition brute portefeuille (scaling pro-rata)
    max_positions: int | None = None   # cap du nombre de positions simultanées
    max_net: float | None = 1.5        # cap d'exposition NETTE (bêta marché), None = libre

    # --- VOL TARGETING PORTEFEUILLE (STRUCTUREL, transformation de risque) ---
    vol_target_annual: float | None = 0.20
    vol_lookback_bars: int = 180       # ~30 jours en H4
    vol_scale_cap: float = 2.0         # on ne lève jamais plus de 2x le levier nominal

    # --- COUTS ---
    fees_roundtrip_pct: float = 0.086  # FRAIS_AR du doc v5, en % du notionnel
    spread_pct: float = 0.02           # spread de base par côté, en %
    spread_mult: float = 3.0           # SPREAD_X du doc v5

    # --- DIVERS ---
    bars_per_year: float = 2190.0      # H4 : 6 bougies/jour * 365
    exclude_tokens: list[str] = field(default_factory=list)

    def cost_per_side_frac(self) -> float:
        """Coût d'un côté (entrée ou sortie) en fraction du notionnel."""
        return (self.fees_roundtrip_pct / 2.0 + self.spread_pct * self.spread_mult) / 100.0

    def to_dict(self) -> dict:
        return asdict(self)

    def copy_with(self, **kw) -> "Config":
        d = self.to_dict()
        d.update(kw)
        return Config(**d)
