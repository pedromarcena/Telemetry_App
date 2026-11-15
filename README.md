# Telemetry_App

<pre style="color: green; font-weight: bold">
                **            **                                                                    
                ##*          *##*                                                                   
                ####*        *#*##*+                                                                
                ##=*##*      *#= +#####**+***##########*+                                           
                ##*  *###***+*#*    +********#**********####****#***#***#****                       
                *#*     *#######+                          *#####***##*#**######*                   
                 ##*                       +**###########*                    +*##*+                
          **     *##*                   *#####*        +##                       *##+               
          *##*    *##*                      **######*###**                        *##               
          *######****##*                           ++                              *#*              
          *##  ***####**                                                           ###              
           *##*                                                    **###########** *##*             
            *###*+                                              +###***        *###*##*             
              *######*+                                      **###*              *####              
           *###***                                          **#######**+          *##*              
        **##*                                                       ***####*+      *#               
      +##**                                                      =*###########+    **               
     *##*                                                    *####***+#+#*#####*                    
    *########*                                             *##*               ***                   
   *****   **###*                                        *##*                                       
          *###**                                        *#*                                         
       *###*                                           ##*                                          
     *##*+                                            *#*                                           
    ##########+                                      *##*                                          =
  *###**+*##*      **                                ###                                          **
 *#*    *#**      **                                 ##*                                         ** 
**    +##*      +##+      *                          ###                                        *#* 
     +##*      +##*       *                           ##*                                      ##*  
    *##*      +##*       **                           +#*                                    *###*  
   *##*      *###        #*        +                   ##*                                 *####*   
  *##+       *##*       *#*        +*                   *#*+                             *###*##    
 *##+       *###        ##+        **                    +##*                          *###=*##     
 *#*       *###*       *##+        ##                      *##**                   +####*  +##+     
 +##*      *###        *##+        *##         +             *####*+**       ***#####*    *##*      
  +##*    +###*        ###+        +#*         #+                *+############***       +##*       
    ##*   *###*       +###*        +##*         #*+                                     *##*        
     *#* *####        *###*        +##*         ###*                                   *#*+         
      *##*#*##        *####        +###*         *###*                               *##*           
        ###*##        *#*##*        ####+         *####*                            ###*            
         ***#*        *####*        *#*##=         *##*##*                       +*##*              
           *###       *##*#*         ##*##          *##+*##*                    *##*                
             +*##*    +##+##+        *#**##+          *##***##*+             **#**                  
                *##*=  ## ##*         *##*##+           *##* *####*+       *##*+                    
                  **##**#**##+         *#*+*#**           *##*+  **####**###*                       
                     *####**#*          *## +##*            +###**    +***                          
                         *+ ###*         *##* *##*             *####*                               
                             **#####***** **##* *##*+ **+***#####*                                  
                                  ****##########* **#####*#** 
                                
                       for: Harpia Aerodesign - by: Pedro Martinez Marcena
</pre>

Aplicativo de visualização da **estação de telemetria Harpia AeroDesign (UFABC)**. Um único arquivo HTML, sem instalação: abre no Chrome ou no Edge, conecta-se à estação de solo pela porta USB (Web Serial) e mostra os seis instrumentos básicos, os parâmetros calculados a partir do pacote de 1024 bits, gráficos, trajetória, comandos, superfícies e a saúde de cada dispositivo. Também reproduz os arquivos gravados pela placa de voo, pela estação ou pelo próprio aplicativo.

| Repositório | Função |
|---|---|
| [Flight_Data_Acquisition_and_Transmission_Unit](../Flight_Data_Acquisition_and_Transmission_Unit) | placa de voo |
| [Ground_Station](../Ground_Station) | estação de solo |
| **Telemetry_App** (este) | aplicativo de visualização |

## Como usar

Abra `index.html` no **Chrome** ou no **Edge** (versão de computador). Para ter as fontes e a leitura de `.xlsx`, o navegador precisa de internet na primeira abertura; sem internet o aplicativo funciona com a fonte do sistema e com arquivos `.bin` e `.csv`. Também pode ser publicado no GitHub Pages.

### Modo nominal

- **Conectar porta serial** — escolha a porta da estação de solo (USB nativa; a taxa em baud é ignorada) ou, na bancada, a porta “UART” da placa de voo a 921 600 baud: a placa espelha 50 pacotes/s no console, sem rádio.
- **Voo de demonstração** — gera no navegador um voo simulado (decolagem, subida, circuito com curvas de 30°, descida e pouso, vento de 3 m/s) e o injeta, já codificado em quadros, no mesmo decodificador usado pela porta serial.
- **Gravar sessão** — salva os bytes recebidos em `sessao_AAAAMMDD_HHMMSS.BIN` (mesmo formato do cartão da estação), para reabrir no replay.
- **Gravar no cartão da estação / Parar gravação da estação** — enviam `MODE REC` e `MODE RX` à estação.

### Modo replay

Arraste para a janela ou abra pelo botão:

| Arquivo | Origem | Conteúdo |
|---|---|---|
| `FLT_nnnn.BIN` | cartão da placa de voo | 2000 pacotes/s; o aplicativo exibe 1 a cada 20 (100 Hz) |
| `GND_nnnn.BIN` | cartão da estação de solo | pacotes recebidos com RSSI/SNR + estados da placa de voo e da estação |
| `sessao_*.BIN` | botão “Gravar sessão” | idem |
| `.csv` exportado | botão “Exportar CSV” | pacote em unidades SI + parâmetros derivados |
| `.csv` / `.xlsx` legado | simulador de voo | colunas `t, phi, theta, psi, Vinf, h, zdot, psidot, xddot, yddot` (graus, `zdot` para cima) |

Barra de espaço reproduz e pausa. **Exportar CSV** grava o voo carregado com todos os campos do pacote e os parâmetros derivados.

Arquivos de exemplo em `samples/`, gerados por `python tools/gen_demo_logs.py`.

## O que é exibido

**Anunciadores** (luzes no topo): estado da placa de voo (mesmas cores do LED RGB da placa), estado da estação, enlace LoRa, enlace de radiocomando, GNSS, gravação no cartão da placa, falhas confirmadas e tensão por célula da bateria de propulsão.

**Seis instrumentos básicos**: velocímetro (velocidade indicada, com a verdadeira em texto), horizonte artificial, altímetro, coordenador de curva (bola calculada pela força lateral no corpo), giro direcional (com o rumo em relação ao solo em magenta) e variômetro.

### Parâmetros calculados a partir do pacote

| Grandeza | Cálculo |
|---|---|
| Densidade do ar | ρ = P / (R T), R = 287,053 J/(kg·K); T do pacote ou temperatura externa informada nos Ajustes |
| Altitude-pressão | h_p = 44 330,77 [1 − (P / 101 325)^0,190263] |
| Altitude-densidade | h_ρ = 44 330,77 [1 − (ρ / 1,225)^0,234969] |
| Desvio da ISA | T − (15 − 0,0065 h_p) |
| Velocidade indicada (EAS) | V∞ √(ρ / 1,225) |
| Pressão dinâmica, Mach | q = ½ ρ V∞², M = V∞ / √(1,4 R T) |
| Fator de carga e força lateral | força específica f = a_NED − g levada ao corpo pela atitude; n = −f_z / g, bola = f_y / g |
| Ângulo de trajetória, ângulo de ataque estimado | γ = atan(v_z / V_solo); α ≈ θ − asen(v_z / V∞) |
| Vento | média móvel de v_solo − V∞ cos θ [cos ψ, sen ψ] |
| Raio e taxa de curva | ψ̇, R = V_solo / |ψ̇| |
| Energia específica | E_h = h + V∞² / 2g; P_s = v_z + V∞ V̇∞ / g |
| Coeficiente de sustentação | C_L = n m g / (q S), com massa e área alar dos Ajustes |
| Potência e energia elétricas | P = U I; mAh e Wh integrados no tempo; tensão por célula |
| Relação potência útil / elétrica | m g P_s / P_m |
| Deflexões | δ = (V − V₀) k, calibração por sensor nos Ajustes (botão “Zerar deflexões”) |
| Latitude e longitude | origem enviada pela placa de voo + posição NED |
| Perda de pacotes | contadores de recebidos e perdidos da estação de solo |

### Ajustes

Massa e área alar (habilitam C_L e potência útil), número de células das baterias, temperatura externa, janela dos gráficos, limites do velocímetro e calibração dos quatro sensores de deflexão. Ficam salvos no navegador.

## Arquivos

```
index.html               o aplicativo
samples/                 voo de demonstração (placa de voo, estação e formato do simulador)
tools/gen_demo_logs.py   gera os arquivos de demonstração
tools/harpia_tlm.py      protocolo em Python (o mesmo dos firmwares)
docs/protocolo.md        pacote, quadros e arquivos
```

## Licença

MIT — ver [LICENSE](LICENSE).
