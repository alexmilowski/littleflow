
class App {
  constructor() {
     this.workflows = {}
  }
  init() {
     // TODO: add pagination
     this.fetchWorkflows(0,50)
  }

  responseFilter(response) {
    if (response.status==401) {
      // Setup auth
      //setTimeout(() => { this.relogin(); },10);
      return null
    } else {
      return response.json()
    }
  }

  fetchWorkflows(start,size) {
    fetch(`service/workflows?next=${start}&size=${size}`)
      .then(response => this.responseFilter(response))
      .then(data => {
         this.addWorkflows(data);
      })
      .catch(error => {
         console.log(error)
      })
  }

  addWorkflows(data) {
     for (let workflow of data) {
        let exists = this.workflows[workflow.id] != null;
        this.workflows[workflow.id] = workflow
        if (exists) {
           // TODO: update UI
        } else {
           let item = $(`<li><a class="uk-accordion-title" href="#"><span class="uk-width-expand" uk-leader>${workflow.id}</span><span class='status'>${workflow.status}</span></a><div class="uk-accordion-content"><div uk-spinner></div></div></li>`).appendTo("#workflows");
           workflow.item = item;
           workflow.loaded = false;
           $(item)
             .find("a")
             .click(() => {
                this.showWorkflowDetails(workflow);
             });

        }
     }
  }

  showWorkflowDetails(workflow) {
     if (!workflow.loaded) {
        this.fetchWorkflowGraph(
           workflow,
           () => {
              this.fetchWorkflowDetails(
                 workflow,
                 () => {
                    this.fetchWorkflowTrace(
                       workflow,
                       () => {
                          workflow.loaded = true
                          this.showWorkflowDetails(workflow)
                       }
                    );
                 }
              )
           }
        )
        return;
     }
     console.log(`Loaded ${workflow.id}`)
     $(workflow.item).find(".uk-accordion-content").empty();
     $(`<div class="mermaid">${workflow.graph.mermaid}</div>`).appendTo($(workflow.item).find(".uk-accordion-content"))
     mermaid.init({}, $(workflow.item).find(".uk-accordion-content .mermaid"));
     // TODO: need a callback from above
     let self = this;
     setTimeout(() => {
        for (let g of $(workflow.item).find('svg .statediagram-state')) {
           let id = g.getAttribute('id')
           let parts = id.split('-');

           // Note: This is a bug in mermaid
           if (parts[1]=='</join></fork>') {
             g.remove();
             continue;
           }
           let [name,index] = parts[1].split(".")
           workflow.graph.tasks[name] = {"element" : g, "id":id, "index": parseInt(index)}
        }
        self.updateGraphForWorkflow(workflow);
     },100);
  }

  updateGraphForWorkflow(workflow) {
     let tasks = workflow.definition[1]
     for (let [timestamp,S] of workflow.S) {
        for (let index in S) {
           let task = tasks[index]
           if (task[0]!="InvokeTask") {
              continue;
           }
           let node = workflow.graph.tasks[task[1].name]
           if (S[index]>0) {
              node.element.classList.add("started")
              console.log(`${index} start`)
           } else if (S[index]<0) {
              node.element.classList.add("started")
              node.element.classList.add("ended")
              console.log(`${index} end`)
           }
        }
     }
  }

  fetchWorkflowDetails(workflow,callback) {
     fetch(`service/workflows/${workflow.id}`)
      .then(response => this.responseFilter(response))
      .then(data => {
         workflow.definition = data
         setTimeout(callback,1)
      })
      .catch(error => {
         console.log(error);
      })
  }
  fetchWorkflowGraph(workflow,callback) {
     fetch(`service/workflows/${workflow.id}/graph`)
      .then(response => response.text())
      .then(data => {
         workflow.graph = { 'mermaid' : data, 'tasks' : {} }
         setTimeout(callback,1)
      })
      .catch(error => {
         console.log(error);
      })
  }
  fetchWorkflowTrace(workflow,callback) {
     fetch(`service/workflows/${workflow.id}/trace/S`)
      .then(response => this.responseFilter(response))
      .then(data => {
         workflow.S = data
         setTimeout(callback,1)
      })
      .catch(error => {
         console.log(error);
      })
  }

}

app = new App()

UIkit.util.ready(function() { app.init(); })
