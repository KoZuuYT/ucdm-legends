"""Mini-games de treino. Importar este pacote registra todos em base.REGISTRY.

Para adicionar um treino novo: crie minigames/meu_treino.py com uma classe
@register, adicione a configuração em assets/data/minigames.json e importe aqui."""
from minigames import agility, focus, shield, slash  # noqa: F401  (registro)
from minigames.base import REGISTRY, TrainingGame  # noqa: F401
