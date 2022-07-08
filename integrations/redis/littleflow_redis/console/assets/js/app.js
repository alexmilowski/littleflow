
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
                    workflow.loaded = true
                    this.showWorkflowDetails(workflow)
                 }
              )
           }
        )
        return;
     }
     console.log(`Loaded ${workflow.id}`)
     $(workflow.item).find(".uk-accordion-content").empty();
     $(`<div class="mermaid">${workflow.graph}</div>`).appendTo($(workflow.item).find(".uk-accordion-content"))
     mermaid.init({}, $(workflow.item).find(".uk-accordion-content .mermaid"));
  }

  fetchWorkflowDetails(workflow,callback) {
     fetch(`service/workflows/${workflow.id}`)
      .then(response => this.responseFilter(response))
      .then(data => {
         workflow.details = data
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
         workflow.graph = data
         setTimeout(callback,1)
      })
      .catch(error => {
         console.log(error);
      })
  }

}

app = new App()

UIkit.util.ready(function() { app.init(); })
