import json

if __name__ == "__main__":
    data = json.load(open("data.json"))
    hs300 = json.load(open("399300.json"))
    output = []
    # optimvar
    optimvars = []
    optimvar_format = "{} = optimvar('{}','LowerBound',0,'UpperBound',1,'Type','continuous');"
    sum_to_1_constraint = []
    for i in range(len(data)):
        optimvars.append(optimvar_format.format(f"x_{i}", f"x_{i}"))
        sum_to_1_constraint.append(f"x_{i}")
    output.extend(optimvars)
    # gain
    gain_format = "gain_{} = {};"
    gains = []
    ziped_data = list(zip(*data.values()))
    last_gain = [0 for _ in range(len(data))]
    for idx, (values) in enumerate(ziped_data):
        assert all([values[i][0] == values[i + 1][0] for i in range(len(values) - 1)])
        cur_gain_output = []
        cur_gain = [last_gain[i] + values[i][1] for i in range(len(data))]
        for i in range(len(data)):
            cur_gain_output.append(f"x_{i} * ({cur_gain[i]})")
        gains.append(gain_format.format(idx, " + ".join(cur_gain_output)))
        last_gain = cur_gain
    output.extend(gains)
    output.append(f"prob = optimproblem('Objective', -gain_{len(gains) - 1});")
    # constraint
    constraints = [f"prob.Constraints.cons = {' + '.join(sum_to_1_constraint)} == 1;"]
    constraints_format = "prob.Constraints.cons_{} = {};"
    for i in range(len(ziped_data)):
        date = ziped_data[i][0][0]
        constraints.append(constraints_format.format(i, f"gain_{i} >= ({hs300[date]})"))
    output.extend(constraints)
    with open("output.txt", "w+") as f:
        f.write("\n".join(output))
        f.write(
"\n\
prob.show();\n\
problem = prob2struct(prob);\n\
[sol,fval,exitflag,output] = linprog(problem);\n\
idx = varindex(prob);\n\
fn = fieldnames(idx);\n\
for key = 1 : length(fn)\n\
    fprintf(\"%s\\t%d\\n\", fn{key}, sol(idx.(fn{key})));\n\
end\
"
        )