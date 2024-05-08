const dataContainer = document.getElementById("data-container");
const issueDiv = document.getElementById("issue");
const filesDiv = document.getElementById("files");
const fullOutputDiv = document.getElementById("full_output");
const select = document.getElementById("instance_id");
const instances = {};

function getIssue(text) {
  // get part of text in <issue> tag
  const issueRegex = /<issue>\s*(.*?)\s*<\/issue>/s;
  const issueMatch = text.match(issueRegex);
  return issueMatch ? issueMatch[1] : "";
}

function getFiles(text) {
  // get all filenames from lines saying [start of <filename>]
  const filenameRegex = /\[start of (.*?)\]/g;
  return Array.from(text.matchAll(filenameRegex), (match) => match[1]);
}

// Function to update displayed data
function updateData(data) {
  issueDiv.textContent = getIssue(data.text);
  filesDiv.innerHTML =
    "<ul>" +
    getFiles(data.text)
      .map((s) => `<li>${s}</li>`)
      .join("") +
    "</ul>";
  fullOutputDiv.textContent = data.full_output;
}

select.addEventListener("change", (event) => {
  const selectedInstanceId = event.target.value;
  if (selectedInstanceId in instances) {
    updateData(instances[selectedInstanceId]);
  }
});

async function go() {
  const response = await fetch("data.jsonl");
  const data = await response.text();
  const lines = data.split("\n");
  for (const line of lines) {
    try {
      const json = JSON.parse(line);
      const instanceId = json.instance_id;
      instances[instanceId] = json;
    } catch {
      // Ignore invalid JSON lines
    }
  }

  // Populate select element with instance IDs (sorted)
  for (const instanceId of Object.keys(instances).sort()) {
    const option = document.createElement("option");
    option.value = instanceId;
    option.textContent = instanceId;
    select.appendChild(option);
  }

  // Select first instance by default
  if (select.options.length > 0) {
    select.value = select.options[0].value;
    updateData(instances[select.value]);
  }
}

go();

// Źródła:
// 1. https://medium.com/samsung-internet-dev/making-an-ar-game-with-aframe-529e03ae90cb
