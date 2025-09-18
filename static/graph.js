const graphData = {
    nodes: [
        { id: "近视", group: 1 },
        { id: "遗传因素", group: 2 },
        { id: "环境因素", group: 2 },
    ],
    links: [
        { source: "近视", target: "遗传因素" },
        { source: "近视", target: "环境因素" },
    ],
};

const svg = d3.select("#graph").append("svg")
    .attr("width", 600)
    .attr("height", 400);

// 绘制节点和关系
// （此处省略 D3.js 的具体实现代码）