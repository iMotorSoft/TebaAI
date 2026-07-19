# Hebrew Manual Search Review Checklist

## Setup

- URL: http://127.0.0.1:3008/login
- Workspace: http://127.0.0.1:3008/research
- Backend: http://127.0.0.1:7008 (health: OK)
- Backend PID: 34406
- Astro PID: 39323
- Branch: `feature/console-backend-core`
- HEAD: `7e9066186318a3323a2df0f66bb9e95ffa61ba07`

## Case 1: Mixed query with Hebrew literal

**Query:** `donde aparece כי יש עון שמעכב תשובה`

**Expected:**
- [x] Interface language detected as `es`
- [x] Primary retrieval language detected as `he`
- [x] Hebrew phrase `עון שמעכב תשובה` extracted as literal phrase
- [x] No evidence returned (phrase not in corpus — LM II only covers lessons 7-16)
- [x] Status: `no_evidence`
- [x] No Spanish result elevated to primary

**Actual:** Correct — `no_evidence`, no false matches.

## Case 2: Pure Hebrew query

**Query:** `כי יש עון שמעכב תשובה`

**Expected:**
- [x] Interface language = `he`
- [x] Primary retrieval = `he`
- [x] No evidence (phrase not in corpus)
- [x] Clean `no_evidence` response

**Actual:** Correct.

## Case 3: Hebrew single word

**Query:** `תפילה`

**Expected:**
- [x] Hebrew detection
- [x] Match found in LM XV
- [x] language_match = `exact`
- [x] literal_match_kind = `exact_phrase`

**Actual:** Correct — found in `lm_xv` with exact match.

## Case 4: Spanish query with Hebrew alias

**Query:** `donde aparece el termino escorpion`

**Expected:**
- [x] Interface = `es`, Primary = `es`
- [x] Spanish results first
- [x] Hebrew aliases (`עקרב`) used as additional search terms

**Actual:** Correct — status OK, Spanish evidence primary.

## Case 5: Spanish relation query

**Query:** `la relacion entre sangre y el habla`

**Expected:**
- [x] Interface = `es`, Primary = `es`
- [x] Both concepts matched
- [x] `direct_relation` for combined match
- [x] Primary evidence correct

**Actual:** Correct — traced to `potencia_plegaria`.

## Case 6: Hebrew filter excluded

**Test:**
- [ ] Desmarcar "Hebreo" en filtros
- [ ] Consultar con frase hebrea
- [ ] Sistema explica contradicción o activa búsqueda hebrea

## Case 7: Non-existent Hebrew phrase

**Query:** `זזזזזזזזז` (nonsense)

**Expected:**
- [x] No forced exact match
- [x] Clean `no_evidence` response
- [x] No invented citation

## Case 8: Mobile view

- [ ] Test evidence order: Hebrew first
- [ ] RTL rendering correct
- [ ] No overflow
- [ ] Page numbers visible

## Overall

- [x] Combining mark fix: PASS
- [x] Backend tests: 827 PASS
- [x] Frontend check: 0 errors
- [x] Frontend build: 7 pages
- [x] Backend active: YES
- [x] Astro active: YES
- [x] URL: http://127.0.0.1:3008/login
- [x] URL: http://127.0.0.1:3008/research
