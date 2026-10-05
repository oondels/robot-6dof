# Cinemática direta offline

A API calcula a pose do último frame de uma cadeia DH a partir da geometria e
dos ângulos físicos das juntas. Não abre serial, lê encoder, habilita torque ou
envia movimento. O cálculo usa apenas a biblioteca padrão de Python; o
carregamento YAML usa `PyYAML==6.0.3`, declarado em `requirements.txt`.

## Convenção e parâmetros

A única convenção suportada é `standard_dh` (Denavit-Hartenberg clássico):

```text
A_i = RotZ(theta_i) · TransZ(d_i) · TransX(a_i) · RotX(alpha_i)
T_0_i = T_0_(i-1) · A_i
theta_i = q_i + theta_offset_i
```

As matrizes atuam sobre vetores-coluna: `p_base = T_base_end · p_end`.
Distâncias são expressas em **milímetros**, ângulos em **graus**. A conversão
para radianos acontece explicitamente antes das funções trigonométricas.
Não há conversão automática de unidades ou suporte a Modified DH.

| Campo por junta | Significado |
|---|---|
| `joint` | Nome exato usado no dicionário de ângulos; independe do ID do servo |
| `theta_offset_deg` | Offset fixo entre o zero físico da aplicação e o zero DH |
| `d_mm` | Translação ao longo de z anterior |
| `a_mm` | Translação ao longo de x após a rotação theta |
| `alpha_deg` | Rotação de twist ao redor de x após as translações |

`q_i` já é um ângulo físico em graus. `Joint.current_angle()` aplica a conversão
de encoder de `JointConfig`, incluindo `zero_position` e `direction`. A FK não
aplica esses valores novamente. A relação aditiva acima exige sentidos positivos
compatíveis entre o ângulo físico e o eixo DH. Um offset não corrige uma inversão
de sentido; essa correspondência precisa ser confirmada antes de usar o modelo
real. Juntas prismáticas não estão incluídas nesta versão.

## Configuração e estado do arm-test1

O destino dos parâmetros reais é
[`robots/arm-test1/config/kinematics.yml`](../robots/arm-test1/config/kinematics.yml).
O carregador recebe diretamente esse caminho; `profile.yml` e `arm_profile.py`
continuam sem implementação. A calibração operacional continua em
`robot_config.py`, sem parâmetros DH em `JointConfig`.

A configuração declara `convention`, `units`, `base_frame`, `end_frame`,
`partial` e `chain`. A sequência `chain` define a ordem das transformações.
Cada entrada contém todos os campos nomeados da tabela acima, sem defaults
geométricos. `partial: true` identifica uma cadeia que cobre apenas parte das
juntas do robô. `partial: false` não certifica precisão, segurança ou um TCP.

O arquivo real contém as cinco linhas fornecidas pelo responsável pelo robô,
na ordem `base_yaw`, `shoulder_pitch`, `elbow_pitch`, `wrist_pitch`, `wrist_roll`.
As distâncias, twists, convenção e unidades foram confirmados. `gripper` não
integra a cadeia de pose; `wrist_roll` está presente porque afeta a orientação.

**A configuração é experimental:** por solicitação do usuário, a leitura de
status fornecida em 2026-10-05 foi adotada como referência da pose simulada.
Os offsets foram calculados por `theta_offset = theta_simulado - q_referencia`,
assumindo sentidos físicos/DH coincidentes. A correspondência entre poses e
os sentidos ainda precisam de validação; a configuração não está certificada
geometricamente.

Os counts, zeros e direções usados estão registrados nos comentários do YAML.
Os ângulos foram recalculados a partir dos counts para preservar a precisão,
em vez de usar os valores arredondados do comando `status`. Alterações na
calibração ou na pose de referência exigem revisar os offsets. O carregador
agora aceita o arquivo; os testes sintéticos validam a matemática, não a
geometria do robô real.

Os nomes `dh_0` e `dh_5` identificam os frames matemáticos inicial e final da
tabela. A relação entre `dh_0` e uma base física/world não foi estabelecida.
O usuário confirmou o uso de **DH 5 como destino**, sem relação comprovada com
o TCP. Não há transformação adicional de ferramenta nem alegação de pose do TCP.

## Exemplo completo sem hardware

Execute na raiz do repositório. Este exemplo usa um **robô planar sintético 2R**
com elos de 100 mm e 50 mm; não usa nem modifica a configuração do arm-test1:

```bash
python3 - <<'PY'
from src.application.kinematics import DHJoint, KinematicConfig, forward_kinematics

config = KinematicConfig(
    convention="standard_dh",
    distance_unit="mm",
    angle_unit="deg",
    base_frame="planar_base",
    end_frame="planar_tip",
    partial=False,
    chain=(
        DHJoint("j1", theta_offset_deg=0, d_mm=0, a_mm=100, alpha_deg=0),
        DHJoint("j2", theta_offset_deg=0, d_mm=0, a_mm=50, alpha_deg=0),
    ),
)
result = forward_kinematics(config, {"j1": 0, "j2": 90})
print("Frame:", result.end_frame, "em", result.base_frame)
print("XYZ (mm):", result.position_mm)  # aproximadamente (100, 50, 0)
print("Rotação:", result.rotation)
print("Transformação final:", result.transform)
for index, (joint, transform) in enumerate(
    zip(result.joint_names, result.accumulated_transforms), start=1
):
    print(f"T_0_{index} após {joint}:", transform)
PY
```

O mesmo modelo sintético pode ser representado em YAML:

```yaml
convention: standard_dh
units:
  distance: mm
  angle: deg
base_frame: planar_base
end_frame: planar_tip
partial: false
chain:
  - joint: j1
    theta_offset_deg: 0
    d_mm: 0
    a_mm: 100
    alpha_deg: 0
  - joint: j2
    theta_offset_deg: 0
    d_mm: 0
    a_mm: 50
    alpha_deg: 0
```

Para carregar um arquivo válido, use:

```python
from src.infrastructure.kinematics_loader import load_kinematic_config
from src.application.kinematics import forward_kinematics

config = load_kinematic_config("/caminho/do/modelo_planar.yml")
result = forward_kinematics(config, {"j1": 0, "j2": 90})
```

## Resultado e contratos

- `transform`: matriz homogênea 4x4 final, do frame final para o inicial.
- `position_mm`: tupla `(x, y, z)` da origem final expressa no frame inicial.
- `rotation`: matriz 3x3 de orientação, extraída da transformação final.
- `accumulated_transforms`: `T_0_1`, ..., `T_0_n`, na ordem de `joint_names`.
- `base_frame`, `end_frame`, `partial`: identificam o alcance do resultado.

As matrizes são tuplas de tuplas de `float`; o resultado e a configuração são
imutáveis. Os frames intermediários são frames DH, não necessariamente centros
visuais de elos ou da carcaça dos servos. Não há extração de Euler nesta versão.

Os ângulos devem conter **exatamente** as juntas da cadeia, com nomes idênticos.
Juntas ausentes, extras, strings, booleanos, NaN e infinito são rejeitados.
Parâmetros geométricos devem ser finitos; valores negativos de `a` e `d` são
permitidos, pois representam deslocamentos orientados. Erros de composição que
excedam a representação finita de `float` também são rejeitados.

O YAML rejeita campos desconhecidos, chaves duplicadas, merges, tags Python,
arquivos vazios e convenções/unidades incompatíveis. Erros de conteúdo são
`ValueError` com o caminho do arquivo; erros de acesso ao arquivo são preservados.
O núcleo usa `TypeError` para tipos inválidos e `ValueError` para valores inválidos.

Para uma futura integração com um braço já inicializado, a seleção é explícita:

```python
measured = arm.current_angles()  # esta etapa consulta o barramento
angles = {link.joint: measured[link.joint] for link in config.chain}
result = forward_kinematics(config, angles)  # esta etapa é puramente matemática
```

Esse trecho não é parte do exemplo offline. Não existe ação `--action fk` ou
integração automática com `RobotArm.get_fkinematics()` nesta feature.

## Testes e limites

```bash
python3 -m unittest tests.test_forward_kinematics tests.test_kinematics_loader -v
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Os testes de FK cobrem transformações individuais, composição espacial,
associação por nome, offsets, frames intermediários, validações, carregamento e
importação sem SDK/serial. As posições analíticas do planar 2R são `(150, 0, 0)`
para `(0°, 0°)`, `(0, 150, 0)` para `(90°, 0°)` e `(100, 50, 0)` para `(0°, 90°)`.
As comparações trigonométricas usam tolerância; o núcleo não arredonda resultados.

A API calcula uma pose geométrica; não verifica limites calibrados, colisões ou
segurança física. Não inclui IK, Jacobiano, trajetórias, controle cartesiano,
dinâmica ou visualização. Uma configuração válida no software ainda precisa de
validação geométrica antes de representar fielmente o braço real.
