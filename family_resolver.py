"""
Family Resolver - Consolidação de Family Members
================================================

Responsabilidade:
- Merge family data de múltiplas fontes (EPO, Google, WIPO)
- Resolver conflitos (prioridade: EPO > Google > WIPO)
- Normalizar country codes
- Gerar estrutura consolidada

NÃO modifica lógica de crawlers existentes.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("family_resolver")


def merge_family_members(
    epo_members: Dict[str, List[Dict]], 
    google_members: Dict[str, List[Dict]]
) -> Dict[str, List[Dict]]:
    """
    Merge family members de EPO e Google
    
    Regra: EPO tem prioridade (API oficial)
           Google complementa países não encontrados no EPO
    
    Args:
        epo_members: {country: [patents]}
        google_members: {country: [patents]}
    
    Returns:
        {country: [patents]} consolidado
    """
    merged = {}
    
    # EPO primeiro (fonte mais confiável)
    for country, patents in epo_members.items():
        merged[country] = patents.copy()
        logger.debug(f"  EPO: {country} → {len(patents)} patents")
    
    # Google complementa países não cobertos por EPO
    for country, patents in google_members.items():
        if country not in merged:
            merged[country] = patents.copy()
            logger.debug(f"  Google: {country} → {len(patents)} patents (new)")
        else:
            # País já existe no EPO - validar se Google tem números adicionais
            epo_numbers = {p.get('patent_number') for p in merged[country]}
            google_additional = [
                p for p in patents 
                if p.get('patent_number') not in epo_numbers
            ]
            
            if google_additional:
                merged[country].extend(google_additional)
                logger.debug(f"  Google: {country} → +{len(google_additional)} additional")
    
    return merged


def extract_country_candidates(
    consolidated_families: Dict[str, Dict[str, List[Dict]]],
    target_countries: List[str]
) -> Dict[str, List[str]]:
    """
    Extrai números de patentes locais para países alvo
    
    Args:
        consolidated_families: {wo_number: {country: [patents]}}
        target_countries: ["BR", "MX", ...]
    
    Returns:
        {country: [patent_numbers]}
    """
    candidates = {country: [] for country in target_countries}
    
    for wo, families in consolidated_families.items():
        for country in target_countries:
            if country in families:
                for patent in families[country]:
                    number = patent.get('patent_number')
                    
                    # Apenas adicionar se tem número válido
                    if number and number != "None":
                        candidates[country].append(number)
    
    # Deduplicate
    for country in candidates:
        candidates[country] = list(set(candidates[country]))
    
    # Log stats
    logger.info(f"📋 Candidates extracted:")
    for country, numbers in candidates.items():
        logger.info(f"   {country}: {len(numbers)} patents")
    
    return candidates
