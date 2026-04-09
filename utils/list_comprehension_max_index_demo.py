"""演示 [index for index, value in enumerate(x) if value == max(x)]"""

x = [3, 5, 7, 3, 7]

print("=" * 50)
print("x =", x)
m = max(x)
print(f"max(x) = {m}")
print()
print("enumerate(x) 逐对 (下标, 元素)，筛出 value == max(x) 的下标 index：")
for index, value in enumerate(x):
    match = value == m
    print(f"  index={index}, value={value}  ->  value == max(x) ? {match}")
print()
result = [index for index, value in enumerate(x) if value == max(x)]
print("列表推导式结果:", result)
print("=" * 50)
