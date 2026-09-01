"""Roteador de intenções (plano, seção 5). Hoje só o nível 0, por regex."""

from device.router.intents import Intent, match, normalize

__all__ = ["Intent", "match", "normalize"]
