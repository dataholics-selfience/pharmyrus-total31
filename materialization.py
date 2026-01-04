"""
Materialization Layer - Target Countries Filter
===============================================

Responsabilidade:
- Filtrar patents baseado em target_countries
- SEM executar novas queries (usa dados já coletados)
- Gerar URLs por país

Princípio: target_countries é critério de MATERIALIZAÇÃO, não de busca.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("materialization")


def generate_url(country: str, patent_number: str) -> str:
    """Gera URL direta para patente no país"""
    if country == "BR":
        number_clean = patent_number.replace("BR", "").replace("A2", "").replace("A", "").replace("B1", "")
        return f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={number_clean}"
    elif country == "US":
        return f"https://patents.google.com/patent/{patent_number}"
    elif country == "EP":
        return f"https://worldwide.espacenet.com/patent/search?q=pn%3D{patent_number}"
    else:
        return f"https://worldwide.espacenet.com/patent/search?q=pn%3D{patent_number}"
