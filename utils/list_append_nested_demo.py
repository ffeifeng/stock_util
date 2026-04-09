"""演示 x.append([3])：末尾追加的是「列表对象」这一项，不会拆开"""

x = [1, 2]

print("=" * 50)
print("初始 x =", x)
print("append 会把括号里的对象整体当作「一个元素」接到列表末尾。")
print("这里参数是列表 [3]，因此 x 会多出一项，该项本身是子列表 [3]。")
print("若写成 extend([3]) 才会把 3 单独接进去，结果不同。")
print()
x.append([3])
print("执行 x.append([3]) 后 x =", x)
print("长度 len(x) =", len(x), "（三个顶层元素：int, int, list）")
print("=" * 50)
