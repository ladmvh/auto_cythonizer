def heavy_loop(n):
    total = 0.0
    for i in range(n):
        for j in range(50):
            total += i*j + i+j  # all arithmetic, no Python functions
    return total
