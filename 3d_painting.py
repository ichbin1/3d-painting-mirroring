import tkinter as tk
from tkinter import messagebox
import math


class GridApp:
    def __init__(self, root):
        self.root = root
        root.title("Зеркалирование фигуры от углов")

        self.width, self.height = 1100, 760
        self.scale = 40.0            # пикселей на 1 мировую единицу (клетку)
        self.min_scale = 4.0
        self.max_scale = 400.0
        self.ox, self.oy = 0.0, 0.0  # смещение world -> screen

        self.canvas = tk.Canvas(root, width=self.width, height=self.height, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        panel = tk.Frame(root, padx=10, pady=10)
        panel.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(panel, text="Управление",
                 font=("Arial", 12, "bold")).pack(pady=(0, 10))
        tk.Button(panel, text="Замкнуть фигуру", width=22,
                  command=self.finish_polygon).pack(pady=3)
        tk.Button(panel, text="Алгоритм 1: отражения", width=22,
                  command=self.run_algorithm).pack(pady=3)
        tk.Button(panel, text="Алгоритм 2: смещение", width=22,
                  command=self.run_offset_algorithm).pack(pady=3)

        offset_frame = tk.Frame(panel)
        offset_frame.pack(fill=tk.X, pady=(0, 3))
        tk.Label(offset_frame, text="Смещение, кл.:").pack(side=tk.LEFT)
        self.offset_step_var = tk.IntVar(value=3)
        tk.Spinbox(offset_frame, from_=1, to=50, width=5,
                   textvariable=self.offset_step_var).pack(side=tk.LEFT, padx=4)

        copies_frame = tk.Frame(panel)
        copies_frame.pack(fill=tk.X, pady=(0, 3))
        tk.Label(copies_frame, text="Копий:").pack(side=tk.LEFT)
        self.offset_count_var = tk.IntVar(value=1)
        tk.Spinbox(copies_frame, from_=1, to=50, width=5,
                   textvariable=self.offset_count_var).pack(side=tk.LEFT, padx=4)

        tk.Button(panel, text="Удалить последнюю точку", width=22,
                  command=self.undo).pack(pady=(10, 3))
        tk.Button(panel, text="Очистить всё", width=22,
                  command=self.clear_all).pack(pady=3)

        tk.Label(panel, text="Вид",
                 font=("Arial", 12, "bold")).pack(pady=(15, 5))
        zf = tk.Frame(panel)
        zf.pack()
        tk.Button(zf, text="−", width=3,
                  command=lambda: self.zoom_at_center(1 / 1.2)).pack(side=tk.LEFT)
        tk.Button(zf, text="+", width=3,
                  command=lambda: self.zoom_at_center(1.2)).pack(side=tk.LEFT)
        tk.Button(zf, text="Сброс вида", width=12,
                  command=self.reset_view).pack(side=tk.LEFT, padx=5)

        self.scale_label = tk.Label(panel, text="Масштаб: 100 %")
        self.scale_label.pack(pady=5)

        # ---- Просмотр "без задних граней" ----
        tk.Label(panel, text="Просмотр",
                 font=("Arial", 12, "bold")).pack(pady=(15, 5))

        self.front_only_var = tk.BooleanVar(value=False)
        tk.Checkbutton(panel, text="Без задних граней",
                       variable=self.front_only_var,
                       command=self._on_front_only_toggle).pack(anchor="w")

        self.hide_intersecting_var = tk.BooleanVar(value=False)
        self.hide_intersecting_check = tk.Checkbutton(
            panel, text="Удалять пересекающиеся грани",
            variable=self.hide_intersecting_var,
            command=self.redraw,
            state=tk.DISABLED)
        self.hide_intersecting_check.pack(anchor="w")

        self.show_labels_var = tk.BooleanVar(value=True)
        tk.Checkbutton(panel, text="Показывать обозначения",
                       variable=self.show_labels_var,
                       command=self.redraw).pack(anchor="w")

        self.visible_edges_var = tk.IntVar(value=3)
        self.visible_edges_scale = tk.Scale(
            panel, from_=1, to=20, orient=tk.HORIZONTAL,
            label="Видимых граней",
            variable=self.visible_edges_var,
            command=lambda _=None: self.redraw())
        self.visible_edges_scale.pack(fill=tk.X)

        tk.Label(panel,
                 text="ЛКМ — точка\n"
                      "ПКМ — замкнуть\n"
                      "Колесо мыши — зум\n"
                      "СКМ + движение — сдвиг",
                 justify="left").pack(pady=20)

        # состояние
        self.points = []          # углы исходной фигуры (в мировых координатах)
        self.finished = False
        self.mirrored = []        # отражённые копии (мировые координаты)
        self.mirror_centers = []  # центры отражений
        self.connections = []     # пары точек для соединительных линий
        self.offset_copies = []       # копии со смещением (мировые координаты)
        self.offset_connections = []  # пары одноимённых углов для копий со смещением

        # события
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Button-3>", self.on_right)
        self.canvas.bind("<MouseWheel>", self.on_wheel)   # Windows / macOS
        self.canvas.bind("<Button-4>",   self.on_wheel)   # Linux, прокрутка вверх
        self.canvas.bind("<Button-5>",   self.on_wheel)   # Linux, прокрутка вниз
        self.canvas.bind("<Button-2>",   self.start_pan)  # средняя кнопка
        self.canvas.bind("<B2-Motion>",  self.do_pan)

        self.reset_view()
        self.redraw()

    # ---------- обработчики переключателей просмотра ----------
    def _on_front_only_toggle(self):
        if self.front_only_var.get():
            self.hide_intersecting_check.config(state=tk.NORMAL)
        else:
            self.hide_intersecting_check.config(state=tk.DISABLED)
            self.hide_intersecting_var.set(False)
        self.redraw()

    # ---------- координаты ----------
    def world_to_screen(self, x, y):
        return x * self.scale + self.ox, y * self.scale + self.oy

    def screen_to_world(self, sx, sy):
        return (sx - self.ox) / self.scale, (sy - self.oy) / self.scale

    def _snap(self, x, y):
        return round(x * 2) / 2, round(y * 2) / 2

    def _ws(self, p):
        return self.world_to_screen(p[0], p[1])

    # ---------- геометрический тест ----------
    @staticmethod
    def _segments_properly_intersect(p1, p2, p3, p4, eps=1e-9):
        """
        True, если отрезки (p1,p2) и (p3,p4) пересекаются во внутренних
        точках (касание концами/вершинами не считается пересечением).
        """
        def orient(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        o1 = orient(p1, p2, p3)
        o2 = orient(p1, p2, p4)
        o3 = orient(p3, p4, p1)
        o4 = orient(p3, p4, p2)

        if (o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps):
            if (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps):
                return True
        return False

    # ---------- вид ----------
    def reset_view(self):
        self.scale = 40.0
        self.ox = self.width / 2
        self.oy = self.height / 2
        self.update_scale_label()
        self.redraw()

    def zoom_at(self, sx, sy, factor):
        wx, wy = self.screen_to_world(sx, sy)
        new_scale = max(self.min_scale,
                        min(self.max_scale, self.scale * factor))
        self.scale = new_scale
        self.ox = sx - wx * self.scale
        self.oy = sy - wy * self.scale
        self.update_scale_label()
        self.redraw()

    def zoom_at_center(self, factor):
        self.zoom_at(self.width / 2, self.height / 2, factor)

    def update_scale_label(self):
        self.scale_label.config(
            text=f"Масштаб: {int(self.scale / 40 * 100)} %")

    def on_wheel(self, event):
        if getattr(event, "num", 0) == 4:
            factor = 1.1
        elif getattr(event, "num", 0) == 5:
            factor = 1 / 1.1
        else:
            factor = 1.1 if event.delta > 0 else 1 / 1.1
        self.zoom_at(event.x, event.y, factor)

    def start_pan(self, event):
        self._pan_start = (event.x, event.y, self.ox, self.oy)

    def do_pan(self, event):
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self.ox = self._pan_start[2] + dx
        self.oy = self._pan_start[3] + dy
        self.redraw()

    # ---------- сетка ----------
    def _draw_grid(self):
        self.canvas.delete("grid")
        x0w, y0w = self.screen_to_world(0, 0)
        x1w, y1w = self.screen_to_world(self.width, self.height)

        ix0, ix1 = math.floor(x0w), math.ceil(x1w)
        iy0, iy1 = math.floor(y0w), math.ceil(y1w)

        for i in range(ix0, ix1 + 1):
            sx, _ = self.world_to_screen(i, 0)
            self.canvas.create_line(sx, 0, sx, self.height,
                                    fill="#c8dcef", tags="grid")
        for j in range(iy0, iy1 + 1):
            _, sy = self.world_to_screen(0, j)
            self.canvas.create_line(0, sy, self.width, sy,
                                    fill="#c8dcef", tags="grid")

        if self.scale >= 18:
            for i in range(ix0 * 2, ix1 * 2 + 1):
                if i % 2 == 0:
                    continue
                sx, _ = self.world_to_screen(i / 2, 0)
                self.canvas.create_line(sx, 0, sx, self.height,
                                        fill="#eaf2fa", tags="grid")
            for j in range(iy0 * 2, iy1 * 2 + 1):
                if j % 2 == 0:
                    continue
                _, sy = self.world_to_screen(0, j / 2)
                self.canvas.create_line(0, sy, self.width, sy,
                                        fill="#eaf2fa", tags="grid")

    # ---------- ввод ----------
    def on_click(self, event):
        if self.finished:
            return
        wx, wy = self.screen_to_world(event.x, event.y)
        x, y = self._snap(wx, wy)
        if self.points and self.points[-1] == (x, y):
            return
        self.points.append((x, y))
        self.redraw()

    def on_right(self, event):
        self.finish_polygon()

    def finish_polygon(self):
        if len(self.points) >= 3 and not self.finished:
            self.finished = True
            self.redraw()

    def undo(self):
        if self.finished:
            self.finished = False
            self.mirrored, self.mirror_centers, self.connections = [], [], []
            self.offset_copies, self.offset_connections = [], []
        if self.points:
            self.points.pop()
        self.redraw()

    def clear_all(self):
        self.points = []
        self.finished = False
        self.mirrored, self.mirror_centers, self.connections = [], [], []
        self.offset_copies, self.offset_connections = [], []
        self.redraw()

    # ---------- видимость "передних" граней ----------
    def _visible_sets(self):
        if not self.front_only_var.get():
            return None
        if not self.mirrored or len(self.points) < 3:
            return None
        n = len(self.points)
        m = len(self.mirrored)
        w = max(1, min(int(self.visible_edges_var.get()), n))
        if w >= n:
            return None

        edges_list = []
        verts_list = []
        for k in range(m):
            edges = set((k + i) % n for i in range(w))
            verts = set((k + i) % n for i in range(w + 1))
            edges_list.append(edges)
            verts_list.append(verts)
        return edges_list, verts_list

    # ---------- отрисовка ----------
    def redraw(self):
        self.canvas.delete("draw")
        self._draw_grid()

        show_labels = self.show_labels_var.get()

        # исходная фигура
        pts_screen = [self._ws(p) for p in self.points]
        if len(pts_screen) >= 2:
            for i in range(len(pts_screen) - 1):
                self.canvas.create_line(*pts_screen[i], *pts_screen[i + 1],
                                        fill="blue", width=3, tags="draw")
            if self.finished:
                self.canvas.create_line(*pts_screen[-1], *pts_screen[0],
                                        fill="blue", width=3, tags="draw")

        for i, (x, y) in enumerate(pts_screen):
            r = 5
            self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                    fill="red", outline="darkred", tags="draw")
            if show_labels:
                self.canvas.create_text(x + 12, y - 12, text=str(i),
                                        fill="darkred",
                                        font=("Arial", 11, "bold"),
                                        tags="draw")

        vis = self._visible_sets()

        # ---- отражённые копии ----
        for k, poly_w in enumerate(self.mirrored):
            poly = [self._ws(p) for p in poly_w]
            n = len(poly_w)

            if vis is None:
                edges_to_draw = list(range(n))
                verts_to_draw = list(range(n))
            else:
                edges_list, verts_list = vis
                edges_to_draw = sorted(edges_list[k])
                verts_to_draw = sorted(verts_list[k])

            # контур копии
            if vis is None:
                coords = [c for p in poly for c in p]
                self.canvas.create_polygon(*coords, outline="green",
                                           fill="", width=2, tags="draw")
            else:
                for j in edges_to_draw:
                    a = poly[j]
                    b = poly[(j + 1) % n]
                    self.canvas.create_line(*a, *b,
                                            fill="green", width=2, tags="draw")

            # центр отражения
            cxw, cyw = self.mirror_centers[k]
            cx, cy = self._ws((cxw, cyw))
            r = 7
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill="yellow", outline="green", tags="draw")

            # видимые вершины копии
            for j in verts_to_draw:
                x, y = poly[j]
                r = 4
                self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                        fill="orange", tags="draw")
                if show_labels:
                    self.canvas.create_text(x + 12, y + 14, text=str(j),
                                            fill="darkgreen",
                                            font=("Arial", 9), tags="draw")

            # ---- подписи рёбер (только видимых) ----
            if show_labels and len(poly) >= 2:
                gx = sum(p[0] for p in poly) / len(poly)
                gy = sum(p[1] for p in poly) / len(poly)
                for j in edges_to_draw:
                    ax, ay = poly[j]
                    bx, by = poly[(j + 1) % n]
                    mx = (ax + bx) / 2.0
                    my = (ay + by) / 2.0
                    dx, dy = mx - gx, my - gy
                    d = math.hypot(dx, dy) or 1.0
                    off = 14.0
                    tx = mx + dx / d * off
                    ty = my + dy / d * off
                    self.canvas.create_text(tx, ty, text=f"e{j}",
                                            fill="green",
                                            font=("Arial", 10, "bold"),
                                            tags="draw")

        # ---- копии со смещением ----
        for poly_w in self.offset_copies:
            poly = [self._ws(p) for p in poly_w]
            coords = [c for p in poly for c in p]
            self.canvas.create_polygon(*coords, outline="green",
                                       fill="", width=2, tags="draw")
            for j, (x, y) in enumerate(poly):
                r = 4
                self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                        fill="orange", tags="draw")
                if show_labels:
                    self.canvas.create_text(x + 12, y + 14, text=str(j),
                                            fill="darkgreen",
                                            font=("Arial", 9), tags="draw")

        # ---- соединительные линии ----
        if vis is None:
            for a_w, b_w in self.connections:
                a = self._ws(a_w)
                b = self._ws(b_w)
                self.canvas.create_line(*a, *b, fill="purple",
                                        width=2, tags="draw")
            for a_w, b_w in self.offset_connections:
                a = self._ws(a_w)
                b = self._ws(b_w)
                self.canvas.create_line(*a, *b, fill="purple",
                                        width=2, tags="draw")
        else:
            edges_list, verts_list = vis
            m = len(self.mirrored)
            n = len(self.points)

            hide_intersecting = self.hide_intersecting_var.get()
            all_visible_edges = []
            if hide_intersecting:
                for k in range(m):
                    poly = [self._ws(p) for p in self.mirrored[k]]
                    for j in edges_list[k]:
                        all_visible_edges.append(
                            (poly[j], poly[(j + 1) % n]))

            for k in range(m):
                nxt = (k + 1) % m
                A = self.mirrored[k]
                B = self.mirrored[nxt]
                vis_k = verts_list[k]
                vis_nxt = verts_list[nxt]
                for j in range(n):
                    if j in vis_k and j in vis_nxt:
                        a = self._ws(A[j])
                        b = self._ws(B[j])

                        if hide_intersecting:
                            crosses = False
                            for e0, e1 in all_visible_edges:
                                if self._segments_properly_intersect(
                                        a, b, e0, e1):
                                    crosses = True
                                    break
                            if crosses:
                                continue

                        self.canvas.create_line(*a, *b, fill="purple",
                                                width=2, tags="draw")

    # ---------- алгоритм ----------
    def run_algorithm(self):
        if not self.finished or len(self.points) < 3:
            messagebox.showwarning(
                "Внимание",
                "Сначала нарисуйте замкнутую фигуру (минимум 3 точки).")
            return

        n = len(self.points)
        cx = sum(p[0] for p in self.points) / n
        cy = sum(p[1] for p in self.points) / n

        # Результат второго алгоритма больше не показываем.
        self.offset_copies, self.offset_connections = [], []

        # 1) От каждого угла Pi зеркалим фигуру (центральная симметрия через Pi)
        items = []
        for i, p in enumerate(self.points):
            mirror = [(2 * p[0] - q[0], 2 * p[1] - q[1]) for q in self.points]
            items.append((i, p, mirror))

        # 2) Сортируем копии, начиная с самой верхней, далее по часовой стрелке.
        items.sort(key=lambda it: (math.atan2(it[1][1] - cy,
                                              it[1][0] - cx) + math.pi / 2)
                                   % (2 * math.pi))

        self.mirror_centers = [it[1] for it in items]
        self.mirrored = [it[2] for it in items]

        # 3) Соединяем одноимённые углы соседних копий по кругу.
        self.connections = []
        m = len(self.mirrored)
        for k in range(m):
            nxt = (k + 1) % m
            A = self.mirrored[k]
            B = self.mirrored[nxt]
            for j in range(n):
                self.connections.append((A[j], B[j]))

        # Подправим верхнюю границу слайдера под n
        try:
            self.visible_edges_scale.config(to=max(1, n))
        except Exception:
            pass

        self.redraw()

    # ---------- алгоритм 2: копии со смещением ----------
    def run_offset_algorithm(self):
        """Копирует фигуру влево и вниз, соединяя одноимённые углы.

        Каждая следующая копия смещена ещё на один шаг влево-вниз;
        углы с одинаковыми номерами соединяются между соседними копиями.
        """
        if not self.finished or len(self.points) < 3:
            messagebox.showwarning(
                "Внимание",
                "Сначала нарисуйте замкнутую фигуру (минимум 3 точки).")
            return

        try:
            step = int(self.offset_step_var.get())
            count = int(self.offset_count_var.get())
        except (tk.TclError, ValueError):
            messagebox.showwarning(
                "Внимание",
                "Смещение и число копий должны быть целыми числами.")
            return

        if step <= 0 or count <= 0:
            messagebox.showwarning(
                "Внимание",
                "Смещение и число копий должны быть положительными.")
            return

        # В мировых координатах ось Y направлена вниз, поэтому
        # «влево и вниз» — это (-step, +step).
        dx, dy = -step, step

        # Результат первого алгоритма больше не показываем.
        self.mirrored, self.mirror_centers, self.connections = [], [], []

        self.offset_copies = []
        self.offset_connections = []
        prev = self.points
        for k in range(1, count + 1):
            copy = [(x + dx * k, y + dy * k) for x, y in self.points]
            self.offset_copies.append(copy)
            for j in range(len(self.points)):
                self.offset_connections.append((prev[j], copy[j]))
            prev = copy

        self.redraw()


if __name__ == "__main__":
    root = tk.Tk()
    app = GridApp(root)
    root.mainloop()