# 🚀 PHARMYRUS v29.6 - CORREÇÕES FINAIS

---

## ✅ O QUE ESTAVA FUNCIONANDO (v29.5)

1. ✅ INPI query 1 é "Darolutamida"
2. ✅ INPI re-login na query 9
3. ✅ Google Patents fazendo buscas diretas em BR

---

## ❌ O QUE AINDA NÃO FUNCIONAVA

1. **Google Patents não encontrava BRs** porque:
   - HTML inicial NÃO tem resultados
   - Precisa aguardar JavaScript carregar!
   
2. **INPI não buscava por brand** porque:
   - Usuário não passou `brand_name` no request
   - Sistema não auto-detectava brand do PubChem

3. **Re-login a cada 8 era muito tarde:**
   - Daniel informou: deve ser a cada 5 buscas

---

## ✅ SOLUÇÕES v29.6

### 1. Google Patents - AGUARDAR JavaScript

**Problema:** HTML renderiza com JavaScript após pageload!

**Solução:**
```python
await page.goto(url, wait_until='networkidle', timeout=30000)

# v29.6: AGUARDAR JavaScript carregar!
await page.wait_for_selector('search-result-item, article, .result', timeout=10000)
await asyncio.sleep(3)  # Renderização completa
```

**Mudanças:**
- `wait_until='networkidle'` em vez de `'domcontentloaded'`
- Espera por elementos de resultado aparecerem
- 3 segundos extra para JavaScript completar
- `num=100` em vez de `num=50`

### 2. INPI - Re-login a cada 5

**Ajustado:**
```python
# ANTES: if (i - 1) % 8 == 0
# DEPOIS: if (i - 1) % 5 == 0

Query 1-5: Sessão ativa
Query 6: 🔄 RE-LOGIN preventivo
Query 6-10: Sessão ativa
Query 11: 🔄 RE-LOGIN preventivo
```

### 3. Brand Auto-Detection

**Novo:**
```python
# v29.6: Auto-detectar brand do PubChem
if not brand and pubchem.get('synonyms'):
    potential_brands = [
        syn for syn in pubchem['synonyms'][:20]
        if len(syn) < 20 and syn[0].isupper() and syn != molecule
    ]
    if potential_brands:
        brand = potential_brands[0]
        logger.info(f"🏷️ Brand auto-detected: {brand}")
```

**Para Darolutamide:**
- PubChem synonyms inclui "Nubeqa"
- Sistema auto-detecta e usa nas buscas!

---

## 🔧 MUDANÇAS NO CÓDIGO

### `google_patents_crawler.py`

**Linha ~290:**
```python
# v29.6: Aguardar JavaScript
await page.goto(url, wait_until='networkidle', timeout=30000)
await page.wait_for_selector('search-result-item, article, .result', timeout=10000)
await asyncio.sleep(3)

# num=100 em vez de 50
url = f"https://patents.google.com/?q={term}&country=BR&num=100"
```

**Linha ~320:**
```python
# v29.6: Múltiplos padrões para BRs
br_patterns = [
    r'BR112\d{10}[A-Z]*\d*',
    r'BRPI\d{7}[A-Z]*\d*',
    r'BR\d{12}[A-Z]*\d*',
]
```

### `inpi_crawler.py`

**Linha ~155:**
```python
# v29.6: Re-login a cada 5 (não 8)
if i > 1 and (i - 1) % 5 == 0:
    logger.info(f"🔄 Query #{i}: RE-LOGIN preventivo (a cada 5 buscas)")
```

### `main.py`

**Linha ~1036:**
```python
# v29.6: Auto-detectar brand
if not brand and pubchem.get('synonyms'):
    potential_brands = [
        syn for syn in pubchem['synonyms'][:20]
        if len(syn) < 20 and syn[0].isupper() and syn != molecule
    ]
    if potential_brands:
        brand = potential_brands[0]
        logger.info(f"🏷️ Brand auto-detected from PubChem: {brand}")
```

---

## 📊 LOGS ESPERADOS

### Google Patents:
```
🟢 LAYER 2: Google Patents (AGGRESSIVE)
   🇧🇷 BUSCA DIRETA BR: https://patents.google.com/?q=darolutamide&country=BR&num=100
      → Aguardando JavaScript renderizar...
   ✅ Novo BR DIRETO: BR112017027822
   ✅ Novo BR DIRETO: BR112018076865
   ✅ Novo BR DIRETO: BR112019014776
   ...

============================================================
🌍 PATENTES POR PAÍS (Google Patents Direct)
============================================================
   BR: 49 patents ← ESPERADO!
============================================================
```

### INPI:
```
🇧🇷 LAYER 3: INPI
   🏷️ Brand auto-detected from PubChem: Nubeqa
   
   🔍 v29.6 DEBUG - Primeiras 10 queries:
      1. 'Darolutamida'
      2. 'darolutamide'
      3. 'Nubeqa' ← AUTO-DETECTADO!
      4. 'nubeqa' (EN)
      5. CAS...
   
   🔍 INPI search 1/5: 'Darolutamida'
   ...
   🔍 INPI search 5/5: ...
   🔄 Query #6: RE-LOGIN preventivo (a cada 5 buscas) ← AJUSTADO!
   ...
```

---

## 🎯 RESULTADO ESPERADO

**Darolutamide v29.6:**

```json
{
  "google_patents": {
    "BRs_direct": 49,  // ← ERA 0!
    "WOs": 101
  },
  "inpi": {
    "BRs_found": 5,  // ← Com brand!
    "re_logins": 2   // ← Queries 6 e 11
  },
  "total_BRs": 54,
  "match_cortellis": "8/8 (100%)",  // ← ESPERADO!
  "rating": "HIGH"
}
```

---

## 📝 VALIDAÇÕES CRÍTICAS

### ✅ Google Patents encontrou BRs?

**Procurar nos logs:**
```
→ Aguardando JavaScript renderizar...
✅ Novo BR DIRETO: BR112...
BR: X patents ← X deve ser > 0!
```

### ✅ Brand foi auto-detectado?

**Procurar nos logs:**
```
🏷️ Brand auto-detected from PubChem: Nubeqa
```

### ✅ INPI re-login a cada 5?

**Procurar nos logs:**
```
🔍 INPI search 5/15: ...
🔄 Query #6: RE-LOGIN preventivo (a cada 5 buscas)
```

---

## ⚠️ SE GOOGLE PATENTS AINDA NÃO ACHAR BRs

**Possíveis causas:**

1. **Timeout aguardando JS:**
   - Aumentar timeout de 10s para 15s
   - Aumentar sleep de 3s para 5s

2. **Seletor errado:**
   - Elemento `search-result-item` pode não existir
   - Testar outros seletores

3. **JavaScript não renderiza em headless:**
   - Rare, mas possível
   - Testar com `headless=False` localmente

**Debug adicional:**
```python
# Salvar HTML após aguardar JS
html_after_js = await page.content()
with open('/tmp/debug-after-js.html', 'w') as f:
    f.write(html_after_js)
```

---

## 🚀 ARQUIVOS MODIFICADOS

- ✏️ `google_patents_crawler.py` - Aguardar JS + num=100
- ✏️ `inpi_crawler.py` - Re-login a cada 5
- ✏️ `main.py` - Auto-detect brand

---

**Versão:** v29.6-FINAL  
**Data:** 2026-01-09  
**Status:** ✅ Correções completas  
**Recall esperado:** 100% (8/8 BRs Cortellis)

---

## 🎯 PRÓXIMOS PASSOS

1. Deploy v29.6
2. Testar com Darolutamide
3. Verificar logs:
   - BRs encontradas pelo Google Patents
   - Brand auto-detectado
   - Re-login a cada 5 queries
4. Se 100% Cortellis ✅ → Testar outras moléculas
5. Se ainda 0% → Debug HTML após JavaScript
