# Cross-reference label convention (controller, 2026-11-12; all section writers use exactly these)
Sections: sec:intro, sec:background, sec:data, sec:methods, sec:results, sec:discussion, sec:conclusion; subsections sec:<section>:<short> (e.g. sec:data:plan, sec:methods:shaping, sec:results:h4). Define the label right after \section / \subsection in your own file.
Figures (file figures/fig_NN_<name>.pdf): fig:design, fig:sample, fig:accuracy, fig:h1bias, fig:h2h3, fig:precool, fig:pstar, fig:dispatch (fig_08_erosion; never call it erosion in text), fig:age, fig:payment, fig:robustness, fig:portfolio, fig:sensitivity, fig:screening; supplement figS:<name>.
Tables: tab:data (T1), tab:methods (compact T2), tab:confirmatory (T3), tab:accuracy (T4), tab:secondary (T5), tab:methodsfull (Table B.1), tab:bridge (S_bridge, supplement).
Equations: eq:<short> (e.g. eq:relmae, eq:pjm, eq:adj, eq:scm, eq:pcross, eq:eta); Appendix B: eq:B<short>.
Algorithms (SPEC s5 wins): body alg:rules, alg:shaping, alg:dispatch, alg:frozen (FrozenEvaluation, final); appendix alg:B1 (sample), alg:B2 (donor), alg:B3 (site inference).
Equations used in Methods: eq:err, eq:relmae, eq:per, eq:site, eq:profile, eq:pjma, eq:ratio, eq:cga, eq:scmw, eq:scmb, eq:inject, eq:sens, eq:pcross, eq:pstar, eq:rho, eq:abserr, eq:eta, eq:h1, eq:h23, eq:sr, eq:hl, eq:sign, eq:tost, eq:holm; appendix eq:B1..eq:B13.
The controller places figure and table environments in main.tex; section writers only \ref them.
