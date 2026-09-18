"""Modele de couts Hyperliquid.

Bareme perp au tier de base (14 j de volume < 5 M$) :
    maker 0.015 %   taker 0.045 %
Funding : horaire, paye directement entre longs et shorts (pas de frais protocole).

On facture systematiquement le taker : une strategie qui suppose des fills maker
suppose aussi un taux de remplissage, ce qui ne se backteste pas honnetement sur
des klines. Le slippage s'ajoute aux frais et couvre le spread + la latence entre
la cloture de la bougie de signal et le fill reel.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoutsHL:
    taker: float = 0.00045       # 4.5 bps, tier de base
    slippage: float = 0.00020    # 2 bps, BTC en taille modeste
    funding_par_heure: int = 8   # le taux Binance est 8 h, HL preleve chaque heure

    @property
    def par_cote(self) -> float:
        """Cout d'un changement de position d'une unite de notionnel."""
        return self.taker + self.slippage

    @property
    def aller_retour(self) -> float:
        return 2 * self.par_cote


HL = CoutsHL()
