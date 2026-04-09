"""演示 [[row[i] for row in vec] for i in range(len(vec[0]))] —— 矩阵转置"""

vec = [[1, 2], [3, 4]]

print("=" * 50)
print("vec =", vec)
print("vec[0] =", vec[0], "-> len(vec[0]) =", len(vec[0]))
print("外层: i in range(len(vec[0]))，即 i = 0, 1")
print()

for i in range(len(vec[0])):
    inner = [row[i] for row in vec]
    print(f"i = {i}:  [row[{i}] for row in vec]")
    for row in vec:
        print(f"         row = {row}  ->  row[{i}] = {row[i]}")
    print(f"       => {inner}")
    print()

result = [[row[i] for row in vec] for i in range(len(vec[0]))]
print("整个表达式结果:", result)
print("（含义：按「列」抽出，得到原矩阵的转置）")
print("=" * 50)
