package com.exceed.analyzer;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.*;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.ast.type.Type;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Collectors;

/**
 * JavaParser 사이드카.
 * 사용: java -jar java-analyzer-sidecar.jar <projectRoot>
 * 출력: stdout 으로 JSON (Python 래퍼가 파싱해 ProjectModel 로 변환).
 *
 * tree-sitter 대비 핵심 차이: SymbolSolver 로 메서드 호출의 소유 타입을 리졸브해
 * resolvedCalls("Owner.method") 를 채운다 → 콜그래프/데드코드 정밀도 향상.
 */
public class AnalyzerMain {

    static final Set<String> SKIP = Set.of("target", "build", "out", "bin",
            ".git", "node_modules", ".gradle", ".idea");

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("usage: java -jar sidecar.jar <projectRoot>");
            System.exit(2);
        }
        Path root = Paths.get(args[0]);

        // 심볼 솔버: 리플렉션(JDK) + 프로젝트 소스. (외부 의존성은 미해결 → try/catch 로 graceful)
        CombinedTypeSolver ts = new CombinedTypeSolver();
        ts.add(new ReflectionTypeSolver());
        findSrcDirs(root).forEach(d -> ts.add(new JavaParserTypeSolver(d)));
        StaticJavaParser.getParserConfiguration().setSymbolResolver(new JavaSymbolSolver(ts));

        Map<String, Object> out = new LinkedHashMap<>();
        List<Object> classes = new ArrayList<>();
        List<List<String>> errors = new ArrayList<>();

        for (Path p : javaFiles(root)) {
            String rel = root.relativize(p).toString();
            try {
                CompilationUnit cu = StaticJavaParser.parse(p);
                String pkg = cu.getPackageDeclaration().map(pd -> pd.getNameAsString()).orElse("");
                List<String> imports = cu.getImports().stream()
                        .map(i -> i.getNameAsString() + (i.isAsterisk() ? ".*" : ""))
                        .collect(Collectors.toList());
                for (TypeDeclaration<?> td : cu.getTypes()) {
                    classes.add(typeToMap(td, pkg, rel, imports));
                }
            } catch (Exception e) {
                errors.add(List.of(rel, e.getClass().getSimpleName() + ": " + e.getMessage()));
            }
        }
        out.put("classes", classes);
        out.put("parseErrors", errors);

        Gson gson = new GsonBuilder().create();
        System.out.println(gson.toJson(out));
    }

    static Map<String, Object> typeToMap(TypeDeclaration<?> td, String pkg, String rel,
                                         List<String> imports) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("name", td.getNameAsString());
        m.put("kind", td.isClassOrInterfaceDeclaration()
                && ((ClassOrInterfaceDeclaration) td).isInterface() ? "interface"
                : td.isEnumDeclaration() ? "enum" : "class");
        m.put("package", pkg);
        m.put("file", rel);
        m.put("imports", imports);
        m.put("annotations", annMap(td.getAnnotations()));

        List<Object> fields = new ArrayList<>();
        for (FieldDeclaration f : td.getFields()) {
            for (VariableDeclarator v : f.getVariables()) {
                Map<String, Object> fm = new LinkedHashMap<>();
                fm.put("name", v.getNameAsString());
                fm.put("type", v.getType().asString());
                fm.put("annotations", annMap(f.getAnnotations()));
                fm.put("modifiers", f.getModifiers().stream()
                        .map(x -> x.getKeyword().asString()).collect(Collectors.toList()));
                fields.add(fm);
            }
        }
        m.put("fields", fields);

        List<Object> methods = new ArrayList<>();
        for (MethodDeclaration md : td.getMethods()) {
            methods.add(methodToMap(md));
        }
        m.put("methods", methods);
        return m;
    }

    static Map<String, Object> methodToMap(MethodDeclaration md) {
        Map<String, Object> mm = new LinkedHashMap<>();
        mm.put("name", md.getNameAsString());
        mm.put("returnType", md.getType().asString());
        mm.put("annotations", annMap(md.getAnnotations()));
        mm.put("modifiers", md.getModifiers().stream()
                .map(x -> x.getKeyword().asString()).collect(Collectors.toList()));

        List<Object> params = new ArrayList<>();
        for (Parameter p : md.getParameters()) {
            Map<String, Object> pm = new LinkedHashMap<>();
            pm.put("name", p.getNameAsString());
            pm.put("type", p.getType().asString());
            pm.put("annotations", annMap(p.getAnnotations()));
            params.add(pm);
        }
        mm.put("params", params);

        List<String> invokes = new ArrayList<>();
        List<String> resolved = new ArrayList<>();
        md.findAll(MethodCallExpr.class).forEach(call -> {
            invokes.add(call.getNameAsString());
            try {
                var rm = call.resolve();   // 심볼 리졸브
                resolved.add(rm.declaringType().getClassName() + "." + rm.getName());
            } catch (Exception ignore) {
                // 외부 의존성/미해결 → resolvedCalls 에 안 넣음 (graceful)
            }
        });
        mm.put("invokes", invokes);
        mm.put("resolvedCalls", resolved);

        List<String> risky = new ArrayList<>();
        md.findAll(CatchClause.class).forEach(c -> {
            String t = c.getParameter().getType().asString();
            if (c.getBody().getStatements().isEmpty()) risky.add("empty");
            else if (t.contains("Exception") || t.contains("Throwable")) risky.add("broad");
        });
        mm.put("riskyCatches", risky);
        return mm;
    }

    static Map<String, Object> annMap(List<? extends AnnotationExpr> anns) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (AnnotationExpr a : anns) {
            Map<String, String> params = new LinkedHashMap<>();
            if (a instanceof SingleMemberAnnotationExpr s) {
                params.put("_value", strip(s.getMemberValue().toString()));
            } else if (a instanceof NormalAnnotationExpr n) {
                n.getPairs().forEach(pair ->
                        params.put(pair.getNameAsString(), strip(pair.getValue().toString())));
            }
            out.put(a.getNameAsString(), params);
        }
        return out;
    }

    static String strip(String s) {
        return s.replaceAll("^\"|\"$", "");
    }

    static List<Path> findSrcDirs(Path root) {
        List<Path> dirs = new ArrayList<>();
        try {
            Files.walk(root, 6)
                .filter(Files::isDirectory)
                .filter(d -> d.toString().replace('\\', '/').endsWith("src/main/java"))
                .forEach(dirs::add);
        } catch (IOException ignore) {}
        if (dirs.isEmpty()) dirs.add(root);
        return dirs;
    }

    static List<Path> javaFiles(Path root) {
        List<Path> files = new ArrayList<>();
        try {
            Files.walk(root)
                .filter(p -> p.toString().endsWith(".java"))
                .filter(p -> Arrays.stream(p.toString().split("[/\\\\]")).noneMatch(SKIP::contains))
                .forEach(files::add);
        } catch (IOException ignore) {}
        return files;
    }
}
