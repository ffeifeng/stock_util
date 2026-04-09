"""演示 x, y, z = sorted([1, 3, 2])：sorted 升序 + 序列解包"""

lst = [1, 3, 2]

print("=" * 50)
print("原列表:", lst)
s = sorted(lst)
print("sorted(lst) 返回新列表（默认升序）:", s)
print()
x, y, z = s
print("解包 x, y, z = 上述结果:")
print(f"  x = {x}")
print(f"  y = {y}")
print(f"  z = {z}")
print()
# 一行写法等价验证
x2, y2, z2 = sorted([1, 3, 2])
print("题目一行写法结果: y =", y2)
print("=" * 50)
