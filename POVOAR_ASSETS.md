# 📸 Povoando o Banco de Assets Locais

Script automatizado para baixar imagens e vídeos do Pexels para o banco local.

---

## 🎯 Uso Rápido

### Baixar imagens de uma tag específica
```bash
python scripts/povoar_assets.py --tag "doctor_doom" --tipo imagem --quantidade 20
```

### Baixar vídeos
```bash
python scripts/povoar_assets.py --tag "marvel" --tipo video --quantidade 10
```

### Povoar múltiplas tags de uma vez
```bash
python scripts/povoar_assets.py --arquivo data/tags_cultura_pop.txt --tipo imagem --quantidade 15
```

---

## 📋 Parâmetros

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `--tag` | Nome da tag (use _ para espaços) | `doctor_doom`, `marvel` |
| `--tipo` | Tipo de asset | `imagem` ou `video` |
| `--quantidade` | Quantos assets baixar | Padrão: 20 |
| `--arquivo` | Arquivo com lista de tags | `tags.txt` |
| `--modo` | Modo de busca | `diversificado` (padrão) ou `simples` |

---

## 🏷️ Tags Prontas para Cultura Pop

Arquivo: `data/tags_cultura_pop.txt`

Contém **40+ tags** organizadas por categoria:

### Marvel
- `doctor_doom`, `marvel`, `iron_man`, `spider_man`, `thor`
- `captain_america`, `hulk`, `black_widow`, `wolverine`, `deadpool`

### DC Comics
- `batman`, `superman`, `joker`, `wonder_woman`, `aquaman`
- `flash`, `harley_quinn`

### Anime/Manga
- `naruto`, `dragon_ball`, `one_piece`, `attack_on_titan`
- `demon_slayer`, `my_hero_academia`, `jujutsu_kaisen`

### Games
- `minecraft`, `fortnite`, `zelda`, `mario`, `pokemon`, `cyberpunk`

### Ficção Científica
- `star_wars`, `star_trek`, `matrix`, `blade_runner`

### Horror
- `scary_movies`, `horror`, `halloween`

### Fantasy
- `lord_of_the_rings`, `harry_potter`, `game_of_thrones`

### Pop Culture Icons
- `pop_art`, `vintage_comics`, `retro_games`

---

## 🚀 Exemplos Práticos

### 1. Povoar banco completo para cultura_pop
```bash
# Baixar 15 imagens para cada tag do arquivo (40+ tags × 15 = 600+ imagens)
python scripts/povoar_assets.py \
  --arquivo data/tags_cultura_pop.txt \
  --tipo imagem \
  --quantidade 15
```

**Tempo estimado:** ~1 hora (respeita rate limits da API Pexels)

### 2. Foco em um nicho específico
```bash
# Marvel (10 tags)
python scripts/povoar_assets.py \
  --arquivo data/tags_cultura_pop.txt \
  --tipo imagem \
  --quantidade 20 \
  | grep -E "(marvel|doctor_doom|iron_man|spider_man|thor|captain_america|hulk|black_widow|wolverine|deadpool)"

# OU criar arquivo específico:
cat > data/tags_marvel.txt << EOF
doctor_doom
marvel
iron_man
spider_man
thor
captain_america
hulk
black_widow
wolverine
deadpool
EOF

python scripts/povoar_assets.py \
  --arquivo data/tags_marvel.txt \
  --tipo imagem \
  --quantidade 20
```

### 3. Banco de vídeos para backgrounds
```bash
# Vídeos de gameplay, natureza, tecnologia
cat > data/tags_videos_background.txt << EOF
gaming_gameplay
technology_abstract
nature_landscape
city_timelapse
space_stars
EOF

python scripts/povoar_assets.py \
  --arquivo data/tags_videos_background.txt \
  --tipo video \
  --quantidade 10
```

---

## ⚠️ Rate Limits do Pexels

**Limites da API gratuita:**
- **200 requisições/hora**
- **30 requisições/minuto**

**O script automaticamente:**
- Aguarda 2.5 segundos entre requisições
- Para ao atingir rate limit (HTTP 429)
- Evita re-baixar arquivos existentes (verifica por hash)

**Se atingir rate limit:**
1. Aguarde 1 hora
2. Ou use outra API key do Pexels
3. Ou continue com as tags restantes depois

---

## 📁 Estrutura de Arquivos

```
data/assets_local/
├── doctor_doom/
│   ├── pexels_7809123_a1b2c3d4e5f6.jpg
│   ├── pexels_7890123_b2c3d4e5f6g7.jpg
│   └── ...
├── marvel/
│   ├── pexels_1234567_c3d4e5f6g7h8.jpg
│   └── ...
├── _download_cache/  # Cache temporário (ignorado pelo pipeline)
└── _fallback_cache/  # Fallback automático do pipeline
```

**Regras:**
- Nome da pasta = nome da tag
- Arquivos nomeados como: `pexels_{ID}_{HASH}.{ext}`
- Pastas com `_` ou `.` no início são ignoradas pelo pipeline

---

## 🔧 Modos de Busca

### Modo Diversificado (padrão)
Busca variações da query para resultados mais variados:
- `{tag}`
- `{tag} art`
- `{tag} wallpaper`
- `{tag} 4k`
- `{tag} aesthetic`

### Modo Simples
Busca apenas pelo nome da tag:
- `{tag}`

---

## 📊 Monitoramento

### Verificar quantos assets foram baixados
```bash
# Por tag
ls -1 data/assets_local/doctor_doom/ | wc -l

# Total geral
find data/assets_local -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.mp4" \) | wc -l

# Tamanho total
du -sh data/assets_local/
```

### Ver estrutura
```bash
tree data/assets_local -L 1
```

---

## 🎨 Dicas Avançadas

### 1. Baixar apenas em alta qualidade
O script já prefere a versão "large" do Pexels (boa qualidade).

### 2. Filtrar por orientação
Modificar `orientation` no script:
```python
params = {
    "query": query,
    "per_page": per_page,
    "page": page,
    "orientation": "landscape",  # ou "portrait" ou "square"
}
```

### 3. Adicionar mais fontes (Pixabay, Unsplash)
O script usa apenas Pexels por enquanto. Para adicionar outras fontes, edite as funções `buscar_pexels_*`.

---

## 🐛 Troubleshooting

### "PEXELS_API_KEY não encontrada"
```bash
# Verificar se está no .env
cat .env | grep PEXELS_API_KEY

# Se não estiver, adicionar:
echo 'PEXELS_API_KEY=sua_chave_aqui' >> .env
```

### "Rate limit atingido"
- Aguarde 1 hora
- Ou use outra API key
- API keys grátis: https://www.pexels.com/api/

### "Nenhum resultado encontrado"
- Tag muito específica? Tente variações
- Verifique se a tag está em inglês
- Tente o modo "diversificado"

### Imagens não aparecem no pipeline
- Verifique se a pasta tem o nome correto da tag
- Tags devem ser minúsculas, sem acentos, espaços viram `_`
- Reinicie o pipeline para reindexar

---

## ✅ Validação

Após povoar, verificar se o pipeline encontra os assets:

```bash
# 1. Verificar se tag existe
ls data/assets_local/doctor_doom/

# 2. Testar casamento de keywords
# O pipeline usa "midia.keywords_busca" do roteiro
# Exemplo: keyword "doctor_doom_art" casa com tag "doctor_doom"

# 3. Executar pipeline de teste
python main.py --run-once

# 4. Verificar logs
grep "Assets resolvidos" logs/pipeline.log
```

---

## 📈 Próximos Passos

1. **Povoar banco inicial:**
   ```bash
   python scripts/povoar_assets.py \
     --arquivo data/tags_cultura_pop.txt \
     --tipo imagem \
     --quantidade 15
   ```

2. **Executar pipeline:**
   ```bash
   python main.py --run-once
   ```

3. **Verificar se usou assets locais:**
   ```bash
   tail -f logs/pipeline.log | grep -E "(Assets|resolvidos|local)"
   ```

4. **Adicionar mais tags conforme necessário:**
   ```bash
   echo "nova_tag" >> data/tags_cultura_pop.txt
   python scripts/povoar_assets.py --tag "nova_tag" --tipo imagem --quantidade 20
   ```
