"""Isolated Qt plotting comparison. Run with the project's .venv Python.

python benchmarks/plot_backends.py --output benchmarks/results
Each backend runs in a separate process. No production code is modified.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE / "_deps"))
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("MPLCONFIGDIR", str(HERE / "results" / "mplconfig"))

BACKENDS = ["pyqtgraph", "pyqtgraph-gl", "matplotlib", "matplotlib-blit",
            "vispy", "qpainter", "qgraphicsview", "opengl", "current-widget"]
COLORS = ["#7cd1a8", "#89b4fa", "#f9c74f", "#f7768e", "#cba6f7"]
WIDTH, HEIGHT = 1000, 900


def stats(values):
    import numpy as np
    return {"median_ms": float(np.median(values)), "p95_ms": float(np.percentile(values, 95)),
            "max_ms": float(max(values))}


def create_backend(name, app):
    import numpy as np
    import pyqtgraph as pg
    from PySide6 import QtCore, QtGui, QtWidgets

    class Base:
        def flush(self):
            target = self.widget.viewport() if hasattr(self.widget, "viewport") else self.widget
            target.repaint()
            app.processEvents()

        def capture(self, path):
            target = self.widget.viewport() if hasattr(self.widget, "viewport") else self.widget
            if hasattr(target,"grabFramebuffer"):
                target.grabFramebuffer().save(str(path))
            else:
                self.widget.grab().save(str(path))

    if name.startswith("pyqtgraph"):
        class PG(Base):
            def __init__(self):
                pg.setConfigOptions(useOpenGL=name.endswith("-gl"), antialias=False)
                self.widget = pg.GraphicsLayoutWidget()
                self.widget.setBackground("#1f2328")
                self.plots, self.curves = [], []
                for i in range(5):
                    p = self.widget.addPlot(row=i, col=0, title=f"Value {i+1}")
                    p.showGrid(x=True, y=True, alpha=.22)
                    p.setLabel("bottom", "Time", units="s")
                    p.setLabel("left", "Value")
                    p.getAxis("bottom").setStyle(maxTickLevel=0)
                    p.getAxis("left").setStyle(maxTickLevel=0)
                    p.disableAutoRange()
                    p.setYRange(-1.2, 1.2, padding=0)
                    c = p.plot(pen=pg.mkPen(COLORS[i], width=1))
                    c.setDownsampling(auto=False)
                    self.plots.append(p)
                    self.curves.append(c)

            def update(self, x, ys, limits):
                for p, c, y in zip(self.plots, self.curves, ys):
                    p.setXRange(*limits, padding=0)
                    c.setData(x=x, y=y, connect="all", skipFiniteCheck=True)

            def flush(self):
                super().flush()
                if name.endswith("-gl"):
                    v = self.widget.viewport()
                    if not v.isValid():
                        raise RuntimeError("No valid pyqtgraph OpenGL context")
                    v.makeCurrent()
                    v.context().functions().glFinish()
                    v.doneCurrent()

            def capture(self, path):
                if not name.endswith("-gl"):
                    return super().capture(path)
                # grabFramebuffer invokes paintGL, but GraphicsView draws via
                # paintEvent; that extra paintGL clears its finished frame.
                from OpenGL import GL
                self.flush()
                v=self.widget.viewport()
                v.makeCurrent()
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,v.defaultFramebufferObject())
                w,h=round(v.width()*v.devicePixelRatioF()),round(v.height()*v.devicePixelRatioF())
                data=GL.glReadPixels(0,0,w,h,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
                QtGui.QImage(data,w,h,QtGui.QImage.Format.Format_RGBA8888).mirrored().save(str(path))
                v.doneCurrent()
        return PG()

    if name.startswith("matplotlib"):
        import matplotlib
        matplotlib.use("qtagg")
        matplotlib.rcParams.update({"path.simplify": False, "lines.antialiased": False})
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

        class MPL(Base):
            def __init__(self):
                self.figure = Figure(figsize=(10, 9), dpi=100, facecolor="#1f2328")
                self.widget = FigureCanvasQTAgg(self.figure)
                self.axes = self.figure.subplots(5, 1)
                self.figure.subplots_adjust(left=.08, right=.97, bottom=.06, top=.97, hspace=.85)
                self.lines = []
                self.limits = None
                self.background = None
                for i, ax in enumerate(self.axes):
                    ax.set_facecolor("#1f2328")
                    ax.set_ylim(-1.2, 1.2)
                    ax.set_title(f"Value {i+1}", fontsize=8, color="white")
                    ax.set_xlabel("Time (s)", fontsize=8, color="white")
                    ax.set_ylabel("Value", fontsize=8, color="white")
                    ax.tick_params(colors="white", labelsize=7)
                    ax.grid(alpha=.22)
                    self.lines.append(ax.plot([], [], color=COLORS[i], linewidth=.72,
                                              animated=name.endswith("blit"))[0])

            def update(self, x, ys, limits):
                changed = self.limits != limits
                for ax, line, y in zip(self.axes, self.lines, ys):
                    if changed:
                        ax.set_xlim(*limits)
                    line.set_data(x, y)
                if name.endswith("blit"):
                    if changed or self.background is None:
                        self.widget.draw()
                        self.background = self.widget.copy_from_bbox(self.figure.bbox)
                    self.widget.restore_region(self.background)
                    for ax, line in zip(self.axes, self.lines):
                        ax.draw_artist(line)
                    self.widget.blit(self.figure.bbox)
                else:
                    self.widget.draw()
                self.limits = limits
        return MPL()

    if name == "vispy":
        from vispy import app as va, scene
        va.use_app("pyside6")

        class Vispy(Base):
            def __init__(self):
                self.canvas = scene.SceneCanvas(keys=None, bgcolor="#1f2328", size=(WIDTH, HEIGHT))
                self.widget = self.canvas.native
                grid = self.canvas.central_widget.add_grid(spacing=8)
                self.views, self.lines = [], []
                self.limits = None
                for i in range(5):
                    sub = grid.add_grid(row=i, col=0)
                    title = scene.Label(f"Value {i+1}", color="white", font_size=8)
                    title.height_max = 20
                    sub.add_widget(title, row=0, col=1)
                    ya = scene.AxisWidget(orientation="left", axis_label="Value", font_size=7)
                    ya.width_max = 65
                    xa = scene.AxisWidget(orientation="bottom", axis_label="Time (s)", font_size=7)
                    xa.height_max = 40
                    sub.add_widget(ya, row=1, col=0)
                    sub.add_widget(xa, row=2, col=1)
                    view = sub.add_view(row=1, col=1, camera="panzoom")
                    ya.link_view(view)
                    xa.link_view(view)
                    scene.visuals.GridLines(color=(.4,.4,.4,.22), parent=view.scene)
                    self.lines.append(scene.visuals.Line(pos=np.zeros((2,2), np.float32),
                                      color=COLORS[i], method="gl", antialias=False, parent=view.scene))
                    self.views.append(view)

            def update(self, x, ys, limits):
                for view, line, y in zip(self.views, self.lines, ys):
                    if self.limits != limits:
                        view.camera.set_range(x=limits, y=(-1.2, 1.2), margin=0)
                    line.set_data(pos=np.column_stack((x, y)).astype(np.float32))
                self.limits = limits

            def flush(self):
                self.canvas.update()
                super().flush()
                self.canvas.set_current()
                from vispy.gloo import gl
                gl.glFinish()
        return Vispy()

    if name in ("qpainter", "qgraphicsview"):
        class Surface(QtWidgets.QWidget):
            paths = []

            def paintEvent(self, event):
                p = QtGui.QPainter(self)
                p.fillRect(self.rect(), QtGui.QColor("#1f2328"))
                draw_paths(p, self.paths)
                p.end()

        def draw_paths(p, paths):
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
            for i, path in enumerate(paths):
                top = i * 180 + 24
                p.setPen(QtGui.QColor("#5c6370"))
                for j in range(5):
                    p.drawLine(70, top+j*30, 970, top+j*30)
                p.setPen(QtGui.QColor("#dce3ea"))
                p.drawText(75, top-5, f"Value {i+1}")
                p.save()
                p.setClipRect(QtCore.QRectF(70, top, 900, 120))
                p.setPen(pg.mkPen(COLORS[i], width=1))
                p.drawPath(path)
                p.restore()

        class Item(QtWidgets.QGraphicsItem):
            paths = []

            def boundingRect(self):
                return QtCore.QRectF(0, 0, WIDTH, HEIGHT)

            def paint(self, painter, option, widget=None):
                draw_paths(painter, self.paths)

        class Painter(Base):
            def __init__(self):
                if name == "qpainter":
                    self.widget = Surface()
                    self.surface = self.widget
                else:
                    self.scene = QtWidgets.QGraphicsScene(0, 0, WIDTH, HEIGHT)
                    self.surface = Item()
                    self.scene.addItem(self.surface)
                    self.widget = QtWidgets.QGraphicsView(self.scene)
                    self.widget.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                    self.widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    self.widget.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    self.widget.setBackgroundBrush(QtGui.QColor("#1f2328"))
                    self.widget.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

            def update(self, x, ys, limits):
                xp = 70 + (x-limits[0]) * 900 / (limits[1]-limits[0])
                # Reuse pyqtgraph's vectorized Qt path conversion, not its plotting machinery.
                self.surface.paths = [pg.arrayToQPath(xp, i*180+84-y*50, connect="all", finiteCheck=False)
                                      for i,y in enumerate(ys)]
        return Painter()

    if name == "opengl":
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        from OpenGL import GL
        from OpenGL.GL.shaders import compileProgram, compileShader

        class GLWidget(QOpenGLWidget):
            vertices = None
            dirty = False

            def initializeGL(self):
                self.program = compileProgram(
                    compileShader("#version 120\nattribute vec2 pos; void main(){gl_Position=vec4(pos,0.,1.);}", GL.GL_VERTEX_SHADER),
                    compileShader("#version 120\nuniform vec3 color; void main(){gl_FragColor=vec4(color,1.);}", GL.GL_FRAGMENT_SHADER))
                self.vbo = GL.glGenBuffers(1)
                self.attr = GL.glGetAttribLocation(self.program, "pos")
                self.color = GL.glGetUniformLocation(self.program, "color")
                self.renderer = GL.glGetString(GL.GL_RENDERER).decode()

            def paintGL(self):
                GL.glClearColor(31/255,35/255,40/255,1)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                if self.vertices is None:
                    return
                GL.glUseProgram(self.program)
                GL.glBindBuffer(GL.GL_ARRAY_BUFFER,self.vbo)
                if self.dirty:
                    GL.glBufferData(GL.GL_ARRAY_BUFFER,self.vertices.nbytes,self.vertices,GL.GL_DYNAMIC_DRAW)
                    self.dirty=False
                GL.glEnableVertexAttribArray(self.attr)
                GL.glVertexAttribPointer(self.attr,2,GL.GL_FLOAT,False,0,ctypes.c_void_p(0))
                GL.glEnable(GL.GL_SCISSOR_TEST)
                dpr=self.devicePixelRatioF()
                for i,c in enumerate(COLORS):
                    top=i*180+24
                    GL.glScissor(int(70*dpr),int((HEIGHT-top-120)*dpr),int(900*dpr),int(120*dpr))
                    color=QtGui.QColor(c)
                    GL.glUniform3f(self.color,color.redF(),color.greenF(),color.blueF())
                    GL.glDrawArrays(GL.GL_LINE_STRIP,i*self.count,self.count)
                GL.glDisable(GL.GL_SCISSOR_TEST)
                GL.glDisableVertexAttribArray(self.attr)
                GL.glBindBuffer(GL.GL_ARRAY_BUFFER,0)
                GL.glUseProgram(0)

        class RawGL(Base):
            def __init__(self):
                self.widget=GLWidget()

            def update(self,x,ys,limits):
                xp=(70+(x-limits[0])*900/(limits[1]-limits[0]))/WIDTH*2-1
                self.widget.vertices=np.concatenate([
                    np.column_stack((xp,1-(i*180+84-y*50)/HEIGHT*2)) for i,y in enumerate(ys)
                ]).astype(np.float32)
                self.widget.count=len(x)
                self.widget.dirty=True

            def flush(self):
                super().flush()
                if not self.widget.isValid():
                    raise RuntimeError("No valid raw OpenGL context")
                self.widget.makeCurrent()
                GL.glFinish()
                self.widget.doneCurrent()

            def capture(self,path):
                self.widget.grabFramebuffer().save(str(path))
        return RawGL()
    raise ValueError(name)


def environment():
    from PySide6 import QtCore
    packages = {}
    for package in ("PySide6", "pyqtgraph", "numpy", "matplotlib", "vispy", "PyOpenGL"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {"python": sys.version, "platform": platform.platform(), "cpu": platform.processor(),
            "qt": QtCore.qVersion(), "packages": packages}


def current_widget(args, app):
    """Separately measure the actual storage + widget path, with one million samples/series."""
    import numpy as np
    from modules.widgets.plot_widget import PlotWidget
    from modules.core.plotter import Plotter
    widget = PlotWidget()
    widget._timer.stop()
    widget.resize(WIDTH, HEIGHT)
    build = time.perf_counter()
    for j in range(5):
        series = Plotter()
        for i in range(args.raw_samples):
            series.add_sample(i*.001, float(np.sin(i*.07+j)))
        widget._series[f"Value {j+1}"] = series
        widget._visible_labels.add(f"Value {j+1}")
    build_seconds = time.perf_counter()-build
    widget._rebuild_plots()
    widget.show()
    app.processEvents()
    rows=[]
    latest=(args.raw_samples-1)*.001
    for mode in ("refresh", "pan_zoom"):
        elapsed=[]
        for k in range(args.frames+10):
            span=latest if mode=="refresh" else latest*(.55+.35*np.sin(k*.12)**2)
            start=0 if mode=="refresh" else (latest-span)*.5
            t=time.perf_counter_ns()
            widget._set_time_range(start,start+span)
            widget.graph.repaint()
            app.processEvents()
            if k>=10:
                elapsed.append((time.perf_counter_ns()-t)/1e6)
        rows.append({"mode":mode, "raw_samples_per_series":args.raw_samples,
                     "plotted_points_per_series":[len(c.xData) for c in widget._curves.values()],
                     **stats(elapsed), "samples_ms":elapsed})
    widget.grab().save(str(args.output/f"{args.worker}.png"))
    # Separate read/downsample/array conversion from rendering.
    from modules.widgets.plot_widget import _prepare_plot_arrays
    costs=[]
    for k in range(args.frames):
        t=time.perf_counter_ns()
        for label,series in widget._series.items():
            _,x,y=series.read_visible_samples(0,latest,widget._bucket_count_for_series(label))
            _prepare_plot_arrays(x,y)
        costs.append((time.perf_counter_ns()-t)/1e6)
    widget.close()
    return {"backend":args.worker, "build_seconds":build_seconds, "rows":rows,
            "storage_read_five_series":stats(costs), "environment":environment()}


def worker(args):
    import numpy as np
    from PySide6 import QtCore, QtGui, QtWidgets
    fmt=QtGui.QSurfaceFormat()
    fmt.setSwapInterval(0)
    fmt.setSamples(0)
    QtGui.QSurfaceFormat.setDefaultFormat(fmt)
    app=QtWidgets.QApplication([])
    errors=[]
    def hook(typ,value,tb):
        errors.append("".join(traceback.format_exception(typ,value,tb)))
        sys.__excepthook__(typ,value,tb)
    sys.excepthook=hook
    if args.worker == "current-widget":
        result=current_widget(args,app)
        if errors:
            raise RuntimeError(errors[0])
        return result
    backend=create_backend(args.worker,app)
    backend.widget.resize(WIDTH,HEIGHT)
    backend.widget.setWindowTitle(f"Plottty benchmark: {args.worker}")
    backend.widget.show()
    app.processEvents()
    rows=[]
    for n in args.points:
        x=np.linspace(0,10,n)
        # Precompute changing data outside the timed interval, identical for every backend.
        datasets=[np.array([.8*np.sin(x*(7+i*2)+k*.09)+.12*np.sin(x*117+k*.17+i)
                           for i in range(5)]) for k in range(args.frames+10)]
        for mode in ("refresh","pan_zoom"):
            times=[]
            for repeat in range(args.repeats):
                for k,ys in enumerate(datasets):
                    limits=(0.,10.) if mode=="refresh" else (float(.4*np.sin(k*.12)),float(9+.6*np.cos(k*.13)))
                    start=time.perf_counter_ns()
                    backend.update(x,ys,limits)
                    backend.flush()
                    elapsed=(time.perf_counter_ns()-start)/1e6
                    if errors:
                        raise RuntimeError(errors[0])
                    if k>=10:
                        times.append(elapsed)
            row={"points_per_series":n,"mode":mode,**stats(times),"samples_ms":times}
            rows.append(row)
            print(args.worker,n,mode,round(row["median_ms"],3),flush=True)
        if n==args.points[0]:
            backend.capture(args.output/f"{args.worker}.png")
    env=environment()
    env.update({"qt_platform":app.platformName(),"device_pixel_ratio":backend.widget.devicePixelRatioF(),
                "logical_size":[backend.widget.width(),backend.widget.height()]})
    if isinstance(getattr(backend.widget,"renderer",None),str):
        env["gl_renderer"]=backend.widget.renderer
    backend.widget.close()
    return {"backend":args.worker,"environment":env,"rows":rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker",choices=BACKENDS)
    parser.add_argument("--backends",nargs="+",choices=BACKENDS,default=BACKENDS)
    parser.add_argument("--points",nargs="+",type=int,default=[1000,10000,100000])
    parser.add_argument("--frames",type=int,default=40)
    parser.add_argument("--repeats",type=int,default=3)
    parser.add_argument("--raw-samples",type=int,default=1000000)
    parser.add_argument("--output",type=Path,default=HERE/"results")
    args=parser.parse_args()
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.worker:
        result=worker(args)
        (args.output/f"{args.worker}.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        return
    failures={}
    for name in args.backends:
        command=[sys.executable,str(Path(__file__).resolve()),"--worker",name,
                 "--output",str(args.output),"--frames",str(args.frames),"--repeats",str(args.repeats),
                 "--raw-samples",str(args.raw_samples),"--points",*[str(n) for n in args.points]]
        try:
            run=subprocess.run(command,capture_output=True,text=True,timeout=600)
            (args.output/f"{name}.log").write_text(run.stdout+run.stderr,encoding="utf-8")
            print(run.stdout,flush=True)
            if run.returncode:
                failures[name]=f"exit {run.returncode}: {run.stderr[-2000:]}"
                print(f"FAILED {name}: {failures[name]}",flush=True)
        except subprocess.TimeoutExpired:
            failures[name]="Timed out after 600 seconds"
    (args.output/"failures.json").write_text(json.dumps(failures,indent=2),encoding="utf-8")
    if failures:
        sys.exit(1)


if __name__=="__main__":
    main()
