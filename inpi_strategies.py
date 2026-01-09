"""
Pharmyrus INPI Multi-Strategy Search Module
============================================

6 estratégias paralelas para maximizar cobertura de patentes BR:
1. Busca textual multi-termo (nome, dev codes, sinônimos)
2. Busca por depositante/titular
3. Busca por IPC/CPC farmacêuticos
4. Busca por janela temporal recente (2023-2025)
5. Busca por formas farmacêuticas
6. Busca por polimorfos e sais

Todas as buscas são feitas em título E resumo no INPI.
"""

import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("pharmyrus.inpi")


class INPIMultiStrategySearch:
    """
    Busca INPI com múltiplas estratégias paralelas
    """
    
    def __init__(
        self,
        molecule_name: str,
        brand_name: Optional[str] = None,
        dev_codes: List[str] = None,
        cas_number: Optional[str] = None,
        applicants: List[str] = None,
        groq_translator = None
    ):
        self.molecule_name = molecule_name
        self.brand_name = brand_name or ""
        self.dev_codes = dev_codes or []
        self.cas_number = cas_number
        self.applicants = applicants or []
        self.groq_translator = groq_translator
        
        # Base URL do crawler INPI
        self.inpi_base_url = "https://crawler3-production.up.railway.app/api/data/inpi/patents"
        
        # Timeout e delays
        self.timeout = 60.0
        self.delay_between_queries = 0.5  # 500ms
        
    async def execute_all_strategies(self) -> Dict[str, Any]:
        """
        Executa todas as 6 estratégias em paralelo
        
        Returns:
            {
                'patents': List[Dict],  # Lista de patentes encontradas
                'audit': Dict,          # Métricas de auditoria
                'strategies': Dict      # Detalhes por estratégia
            }
        """
        logger.info("🚀 Iniciando INPI Multi-Strategy Search")
        logger.info(f"   Molécula: {self.molecule_name}")
        logger.info(f"   Brand: {self.brand_name or 'N/A'}")
        logger.info(f"   Dev codes: {len(self.dev_codes)}")
        
        # Executar todas as estratégias
        strategies = [
            self._strategy_1_textual_multiterm(),
            self._strategy_2_applicant(),
            self._strategy_3_ipc_pharmaceutical(),
            self._strategy_4_temporal_recent(),
            self._strategy_5_formulations(),
            self._strategy_6_polymorphs_salts(),
        ]
        
        results = await asyncio.gather(*strategies, return_exceptions=True)
        
        # Consolidar resultados
        all_patents = []
        strategy_details = {}
        
        for idx, result in enumerate(results, 1):
            strategy_name = f"strategy_{idx}"
            
            if isinstance(result, Exception):
                logger.error(f"❌ Estratégia {idx} falhou: {result}")
                strategy_details[strategy_name] = {
                    'name': self._get_strategy_name(idx),
                    'status': 'failed',
                    'error': str(result),
                    'patents_found': 0
                }
                continue
            
            patents, metadata = result
            strategy_details[strategy_name] = metadata
            all_patents.extend(patents)
        
        # Deduplicate
        unique_patents = self._deduplicate_patents(all_patents)
        
        logger.info(f"✅ Total patentes encontradas: {len(unique_patents)}")
        logger.info(f"   (deduplicated from {len(all_patents)} raw results)")
        
        return {
            'patents': unique_patents,
            'strategies': strategy_details,
            'summary': {
                'total_strategies': 6,
                'successful_strategies': sum(1 for s in strategy_details.values() if s['status'] == 'success'),
                'total_patents_raw': len(all_patents),
                'total_patents_unique': len(unique_patents)
            }
        }
    
    def _get_strategy_name(self, idx: int) -> str:
        """Retorna nome descritivo da estratégia"""
        names = {
            1: "Textual Multi-Term",
            2: "Applicant/Titular",
            3: "IPC/CPC Pharmaceutical",
            4: "Temporal Recent (2023-2025)",
            5: "Formulations",
            6: "Polymorphs & Salts"
        }
        return names.get(idx, f"Strategy {idx}")
    
    # ============================================
    # ESTRATÉGIA 1: BUSCA TEXTUAL MULTI-TERMO
    # ============================================
    
    async def _strategy_1_textual_multiterm(self) -> tuple[List[Dict], Dict]:
        """
        Busca usando:
        - Nome da molécula
        - Dev codes
        - Nome comercial
        - Combinações
        
        Busca em: título E resumo
        """
        logger.info("📝 Estratégia 1: Textual Multi-Term")
        
        queries = []
        
        # Query 1: Nome principal
        queries.append({
            'term': self.molecule_name,
            'label': 'molecule_name',
            'field': 'both'  # título + resumo
        })
        
        # Query 2: Nome comercial (se disponível)
        if self.brand_name:
            queries.append({
                'term': self.brand_name,
                'label': 'brand_name',
                'field': 'both'
            })
        
        # Query 3-N: Dev codes
        for idx, dev_code in enumerate(self.dev_codes[:5], 1):  # Max 5 dev codes
            queries.append({
                'term': dev_code,
                'label': f'dev_code_{idx}',
                'field': 'both'
            })
        
        # Query: Combinação molécula + brand
        if self.brand_name:
            queries.append({
                'term': f"{self.molecule_name} {self.brand_name}",
                'label': 'molecule_brand',
                'field': 'both'
            })
        
        # Executar queries
        patents = await self._execute_inpi_queries(queries)
        
        metadata = {
            'name': 'Textual Multi-Term',
            'status': 'success',
            'queries_executed': len(queries),
            'patents_found': len(patents),
            'queries_detail': [
                {'term': q['term'], 'label': q['label'], 'count': len([p for p in patents if p.get('source') == f"inpi_textual_{q['label']}"])}
                for q in queries
            ]
        }
        
        logger.info(f"   ✅ Estratégia 1: {len(patents)} patentes")
        return patents, metadata
    
    # ============================================
    # ESTRATÉGIA 2: BUSCA POR DEPOSITANTE/TITULAR
    # ============================================
    
    async def _strategy_2_applicant(self) -> tuple[List[Dict], Dict]:
        """
        Busca usando nomes de depositantes conhecidos
        
        Nota: Precisa ter lista de depositantes da molécula
        """
        logger.info("🏢 Estratégia 2: Applicant/Titular")
        
        if not self.applicants:
            logger.info("   ⚠️  Sem depositantes conhecidos, pulando")
            return [], {
                'name': 'Applicant/Titular',
                'status': 'skipped',
                'reason': 'no_applicants_provided',
                'patents_found': 0
            }
        
        queries = []
        for idx, applicant in enumerate(self.applicants[:10], 1):  # Max 10
            # Buscar titular + molécula (para filtrar ruído)
            queries.append({
                'term': f"{applicant} {self.molecule_name}",
                'label': f'applicant_{idx}',
                'field': 'both'
            })
        
        patents = await self._execute_inpi_queries(queries)
        
        metadata = {
            'name': 'Applicant/Titular',
            'status': 'success',
            'queries_executed': len(queries),
            'patents_found': len(patents)
        }
        
        logger.info(f"   ✅ Estratégia 2: {len(patents)} patentes")
        return patents, metadata
    
    # ============================================
    # ESTRATÉGIA 3: BUSCA POR IPC/CPC FARMACÊUTICO
    # ============================================
    
    async def _strategy_3_ipc_pharmaceutical(self) -> tuple[List[Dict], Dict]:
        """
        Busca usando classificações IPC farmacêuticas:
        - A61K: Medicamentos
        - A61P: Atividade terapêutica
        - A61K9: Formas de dosagem
        - A61K31: Compostos orgânicos
        - A61K47: Excipientes
        """
        logger.info("🔬 Estratégia 3: IPC/CPC Pharmaceutical")
        
        ipc_codes = [
            ('A61K', 'medicamentos'),
            ('A61P', 'atividade_terapeutica'),
            ('A61K9', 'formas_dosagem'),
            ('A61K31', 'compostos_organicos'),
            ('A61K47', 'excipientes'),
        ]
        
        queries = []
        for ipc_code, label in ipc_codes:
            # Buscar IPC + molécula
            queries.append({
                'term': f"{self.molecule_name} {ipc_code}",
                'label': f'ipc_{label}',
                'field': 'both'
            })
        
        patents = await self._execute_inpi_queries(queries)
        
        metadata = {
            'name': 'IPC/CPC Pharmaceutical',
            'status': 'success',
            'queries_executed': len(queries),
            'patents_found': len(patents)
        }
        
        logger.info(f"   ✅ Estratégia 3: {len(patents)} patentes")
        return patents, metadata
    
    # ============================================
    # ESTRATÉGIA 4: BUSCA TEMPORAL RECENTE
    # ============================================
    
    async def _strategy_4_temporal_recent(self) -> tuple[List[Dict], Dict]:
        """
        Busca focada em patentes recentes (2023-2025)
        
        Justificativa: EPO tem lag de 6-18 meses
        """
        logger.info("📅 Estratégia 4: Temporal Recent (2023-2025)")
        
        # INPI não aceita filtro de data na URL diretamente
        # Vamos buscar a molécula e filtrar depois por data
        queries = [
            {
                'term': self.molecule_name,
                'label': 'temporal_2023_2025',
                'field': 'both',
                'filter_date_after': '2023-01-01'
            }
        ]
        
        patents = await self._execute_inpi_queries(queries)
        
        # Filtrar por data no resultado
        recent_patents = []
        for patent in patents:
            filing_date = patent.get('filing_date', '')
            if filing_date and filing_date >= '2023-01-01':
                recent_patents.append(patent)
        
        metadata = {
            'name': 'Temporal Recent (2023-2025)',
            'status': 'success',
            'queries_executed': len(queries),
            'patents_found': len(recent_patents),
            'date_filter': '2023-01-01 onwards'
        }
        
        logger.info(f"   ✅ Estratégia 4: {len(recent_patents)} patentes")
        return recent_patents, metadata
    
    # ============================================
    # ESTRATÉGIA 5: BUSCA POR FORMAS FARMACÊUTICAS
    # ============================================
    
    async def _strategy_5_formulations(self) -> tuple[List[Dict], Dict]:
        """
        Busca usando termos de formulação farmacêutica
        
        Baseado em: Cortellis Patent Type = "Formulation"
        """
        logger.info("💊 Estratégia 5: Formulations")
        
        # Termos dinâmicos (não específicos de uma molécula)
        formulation_terms = [
            'comprimido',
            'capsula',
            'injetavel',
            'formulacao',
            'composicao farmaceutica',
            'liberacao controlada',
            'liberacao sustentada',
            'forma farmaceutica',
        ]
        
        queries = []
        for idx, term in enumerate(formulation_terms[:8], 1):  # Max 8
            queries.append({
                'term': f"{self.molecule_name} {term}",
                'label': f'formulation_{idx}',
                'field': 'both'
            })
        
        patents = await self._execute_inpi_queries(queries)
        
        metadata = {
            'name': 'Formulations',
            'status': 'success',
            'queries_executed': len(queries),
            'patents_found': len(patents)
        }
        
        logger.info(f"   ✅ Estratégia 5: {len(patents)} patentes")
        return patents, metadata
    
    # ============================================
    # ESTRATÉGIA 6: BUSCA POR POLIMORFOS E SAIS
    # ============================================
    
    async def _strategy_6_polymorphs_salts(self) -> tuple[List[Dict], Dict]:
        """
        Busca usando termos de polimorfos, sais e formas cristalinas
        
        Baseado em: Cortellis Patent Type = "Product derivative"
        """
        logger.info("🧬 Estratégia 6: Polymorphs & Salts")
        
        # Termos dinâmicos (não específicos de uma molécula)
        derivative_terms = [
            'polimorfo',
            'forma cristalina',
            'sal',
            'hidrato',
            'solvato',
            'anidro',
            'cloridrato',
            'sulfato',
            'fosfato',
            'cristal',
        ]
        
        queries = []
        for idx, term in enumerate(derivative_terms[:10], 1):  # Max 10
            queries.append({
                'term': f"{self.molecule_name} {term}",
                'label': f'derivative_{idx}',
                'field': 'both'
            })
        
        patents = await self._execute_inpi_queries(queries)
        
        metadata = {
            'name': 'Polymorphs & Salts',
            'status': 'success',
            'queries_executed': len(queries),
            'patents_found': len(patents)
        }
        
        logger.info(f"   ✅ Estratégia 6: {len(patents)} patentes")
        return patents, metadata
    
    # ============================================
    # HELPER: EXECUTAR QUERIES NO INPI
    # ============================================
    
    async def _execute_inpi_queries(self, queries: List[Dict]) -> List[Dict]:
        """
        Executa múltiplas queries no INPI de forma sequencial com delay
        
        Args:
            queries: Lista de {'term': str, 'label': str, 'field': str}
        
        Returns:
            Lista de patentes encontradas
        """
        all_patents = []
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for idx, query in enumerate(queries, 1):
                term = query['term']
                label = query['label']
                
                try:
                    # Buscar em título E resumo (o crawler INPI busca em ambos por padrão)
                    url = f"{self.inpi_base_url}?medicine={term}"
                    
                    logger.debug(f"   Query {idx}/{len(queries)}: {term}")
                    
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    if data and 'data' in data and isinstance(data['data'], list):
                        patents = data['data']
                        
                        # Processar cada patente
                        for patent in patents:
                            processed = self._process_inpi_patent(patent, label)
                            if processed:
                                all_patents.append(processed)
                        
                        logger.debug(f"      → {len(patents)} patentes encontradas")
                    
                except Exception as e:
                    logger.warning(f"   ⚠️  Query '{term}' falhou: {e}")
                    continue
                
                # Delay entre queries
                if idx < len(queries):
                    await asyncio.sleep(self.delay_between_queries)
        
        return all_patents
    
    def _process_inpi_patent(self, raw_patent: Dict, source_label: str) -> Optional[Dict]:
        """
        Processa patente bruta do INPI para formato padrão
        
        Args:
            raw_patent: Resposta bruta do INPI
            source_label: Label da estratégia que encontrou
        
        Returns:
            Patent dict ou None se inválida
        """
        try:
            # Validar campos essenciais
            if not raw_patent.get('title') or not raw_patent.get('title', '').startswith('BR'):
                return None
            
            patent_number = raw_patent['title'].replace(' ', '-')
            
            return {
                'patent_number': patent_number,
                'title': raw_patent.get('applicant', ''),
                'abstract': raw_patent.get('fullText', ''),
                'filing_date': raw_patent.get('depositDate', ''),
                'applicants': [raw_patent.get('applicant', '')] if raw_patent.get('applicant') else [],
                'source': f"inpi_{source_label}",
                'link_nacional': f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={raw_patent['title']}",
                'country': 'BR'
            }
        
        except Exception as e:
            logger.warning(f"   Erro processando patente INPI: {e}")
            return None
    
    def _deduplicate_patents(self, patents: List[Dict]) -> List[Dict]:
        """
        Remove duplicatas baseado em patent_number
        """
        seen = set()
        unique = []
        
        for patent in patents:
            patent_number = patent.get('patent_number', '').upper().replace('-', '').replace(' ', '')
            
            if patent_number and patent_number not in seen:
                seen.add(patent_number)
                unique.append(patent)
        
        return unique
