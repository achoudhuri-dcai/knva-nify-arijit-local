/* 
This script is one of several components that perform the streaming of the LLM response. These components are:

1. The python Dash app that calls the LLM and streams the response to the browser.  
2. The Dash chat_bot() callback that uses steamIO to send LLM chuncks to the browser. 
       It calls the LLM which returns a python generator that yeilds small text strings, about one word in size.
       These little "chunks" are concatenated into a "merged_chunk" 
       Merged chuncks are sent to the browser using the emit function of the flash_socketio library.
       The emit function sends the merged chunk to the browser as a string via the socketio connection.
3. The socketio connection that is used to send the merged chunk to the browser.
4. A client side callback running in the browser that receives the merged chunk string and concatenates it to window.aiwBuffer.
       This callback is defined in the python code and looks like this:       
           clientside_callback(
               """(word) => {
               window.aiwBuffer += word;
               return "";
               }""",
               Output("results", "children", allow_duplicate=True),
               Input("socketio", "data-stream"),
               prevent_initial_call=True,    
            )
        It is a client side callback that is used to receive the merged chunk string and concatenate it to window.aiwBuffer.
5. The markdown-it library is used to render the markdown to html. This is a lightweight library that is used to render markdown to html.
       It is included at the time the Dash app is intialized in the python code, like this: 
           flask_server, app = instantiate_app(
               app_title, 
               external_stylesheets,
               external_scripts=['https://cdnjs.cloudflare.com/ajax/libs/markdown-it/13.0.2/markdown-it.js'],
6. This file custom_script.js, from the assest folder, which runs in the browser and is used to process the merged chunk and render it to html.
       It monitors the buffer and renders the markdown to html using the markdown-it library.
       It also uses the performance API to measure the time it takes to render the markdown to html - for debugging and performance testing.
       It containts a top level call to the function monitorBuffer() that is executed when the browser has fully loaded the client side parts of Dash.
           MonitorBuffer() initializes the variables and clears window.aiwBuffer.
           It also sets references to two elements that are used to display the text and markdown.
               fulltext - the element where the chat_bot outputs the complete LLM response - this element is styled as display:none
               markdown - the element where the markdown converted to html is displayed - incrementally as the LLM response is streamed to the browser.
       In each interval, the function checks if the buffer has changed and if so, it processes the buffer and renders the text to html.
       It also checks if the end of the text marker is found and if so, it waits 2 intervals then renders the full text to html, 
           replacing the incrementally rendered response . 
      
*/
function monitorBuffer() {
  var buffer_len = 0;
  var pointer = -1;       // the pointer to the end point in the text to be rendered. This is increnmented word by word until the end of the text is reached
  var textContent = ""; 
  var textToRender = ""; 
  const endOfTextMarker = "END$$$END"; // marker for the end of the text
  const checkBufferInterval = 45; // interval to check the buffer in milliseconds
  var endOfTextCount = 0; // counter for the end of text marker
  var fulltextMissingCount = 0; // the counter for the fulltext contents not found
  var fulltext            // element where the text is displayed
  var markdown            // element where html <= markdown is displayed
  var currentURL = "";    // used to check if the URL has changed
  window.aiwBuffer = "";  // buffer that is updated by the DASH streamIO callback
  msgLevel = 0;        // message level for logging
  // PERFORMANCE DATA
  var perf = {
    start: 0,        // start time of the rendering process 
    end: 0,          // end time of the rendering process
    duration: 0,     // duration of the rendering process
    count: 0,        // number of times the rendering process is called
    avg: 0,          // average time of the rendering process
    max: 0,          // maximum time of the rendering process
    sum: 0,          // sum of the times of the rendering process
  };
  // MARKDOWN LIBRARY
  // the markdownit library is used to render markdown to html. This is a lightweight library that is used to render markdown to html.
  // it is included at the time the Dash app is intialized in the python code, like this:
  //    app = Dash(__name__, 
  //       external_scripts=['https://cdnjs.cloudflare.com/ajax/libs/markdown-it/13.0.2/markdown-it.js'],
  //       external_stylesheets=dmc.styles.ALL)
  const md = markdownit()

  
  // good test query that creates several markdown elements:  Elaborate on the top 10 national parks in the world
  
  setInterval(() => {      // run the function with delay specified in setInterval second argument
    processBuffer();       // call the function to process the buffer
  }, checkBufferInterval); // every few milliseconds (50-75ms is a good value )

  function processBuffer() {  
    perf.start = performance.now();  // start the performance timer
    const now = new Date();        
      
    // confirm the required elements are available.  Return if any are not found.  The closing else at the end of this function will recheck for the elements.
    // this is important because the elements are not available until the Dash app is fully loaded.  This takes a few seconds.

    fulltext = document.getElementById("results-fulltext");      // this is the element where the Dash app sets the fulltext
    markdown = document.getElementById("results-markdown");      // this is the element where html (from markdown) is displayed   
    input    = document.getElementById("human-chat-text-area");  // get the input element
    
    if (!fulltext) {  // check if elements exist because it takes a while to load all the parts of the page
      if (msgLevel >= 1) console.log(now.toISOString(), 'fulltext element not found');  // log when fulltext is not found
      return;  // return if fulltext is not found 
    }
    if (!markdown) {   // check if elements exist because it takes a while to load all the parts of the page
      if (msgLevel >= 1) console.log(now.toISOString(),'markdown element not found');  // log when markdown is not found
      return;  // return if markdown is not found 
    }

    // clear the markdown element if the URL has changed
    if (currentURL != window.location.href) {  // check if the URL has changed
      currentURL = window.location.href;  // update the current URL 
      // clear the markdown element
      console.log(now.toISOString(), 'URL changed - clearing markdown element');  // log when URL changes
      markdown.innerHTML = "";  // clear the markdown element
    }

    if (fulltext && markdown && input) {  // check if elements exist because it takes a while to load all the parts of the page
      
      if (window.aiwBuffer.length > 0) {
        // ### start of buffer processing
        textContent = window.aiwBuffer // buffer.textContent;
        if (buffer_len != textContent.length) {            // has the buffer length has changed since the last time?
          if (buffer_len < 1 && textContent.length > 0) {  // is this a new response?
            if (msgLevel >= 0) console.log(now.toISOString(), 'receiving new response:' , textContent);  
            markdown.innerHTML = "<p>" + textContent + "</p>";                       // clear the markdown element
            fulltext.innerHTML = "";                       // clear the fulltext element
            endOfTextCount = 0;                            // reset the end of text counter
          }
          buffer_len = textContent.length                             // update buffer length
          //console.log(now.toISOString(), 'buffer_len:', buffer_len);  // log when buffer length changes
        }
        if (buffer_len > pointer) {                        // is there more text to process?
          let spaceIndex = textContent.indexOf(" ", pointer + 1);
          if (spaceIndex > 0) {
            if (msgLevel >= 1) console.log(now.toISOString(), textContent.slice(Math.max(pointer, 0), spaceIndex));  // log the word
            pointer = spaceIndex;
          } else {
            if (msgLevel >= 1) console.log(now.toISOString(), textContent.slice(pointer));  // log the last words
            if (msgLevel >= 1) console.log(now.toISOString(), 'at end of buffer');
            pointer = textContent.length;
          }    
          
          textToRender = textContent.slice(0,pointer);    // get the text to render. This grows word by word until the end of the text is reached
          
          if (textToRender.endsWith(endOfTextMarker)) {   // check if the end of the text is reached
            // end of text marker found
            endOfTextCount = 1;  // set the end of text counter to signal that the end of text is reached
            textToRender = textToRender.slice(0, -endOfTextMarker.length);  // remove the end of text marker
            rendered = md.render(textToRender);  // render trimmed markdown to html
            markdown.innerHTML = rendered;  // set the html to the markdown element
            if (msgLevel >= 1) console.log(now.toISOString(), 'end of text reached');  // log when end of text is reached
            // reset things
            window.aiwBuffer = "";  // reset the buffer  - this block of code will not execute until the next time the Dash app sends a new response
            pointer = -1;           // reset the pointer
            buffer_len = 0;         // reset the buffer length
          } else {
            rendered = md.render(textToRender);  // render trimmed markdown to html
            markdown.innerHTML = rendered;  // copy the html to the markdown element
            if (msgLevel >= 2) console.log(textToRender.slice(-90));  // log the last 20 characters of the text to render
            if (msgLevel >= 2)console.log(rendered.slice(-90));  // log the last 20 characters of the text to render
          }
        }         
        perf.end = performance.now();  // end the performance timer
        perf.duration = perf.end - perf.start;  // calculate the duration of the rendering process
        perf.count++;  // increment the count of the rendering process
        perf.max = Math.max(perf.max, perf.duration);  // calculate the maximum time of the rendering process
        perf.sum += perf.duration;  // calculate the sum of the times of the rendering process
        perf.avg = perf.sum / perf.count;  // calculate the average time of the rendering process
        // ### end of buffer processing
      }     
      
      if (endOfTextCount > 0) {  // check if the end of text marker was found
        // ### start of endOfText marker processing
        if (msgLevel >= 1) console.log(now.toISOString(), 'end of text marker found', endOfTextCount);  // log when end of text marker is found
         // log and reset the performance data when endOfTextCount equals 1
        if (endOfTextCount == 1) {  // check if the end of text marker was found  
          if (msgLevel >= 0) console.log(now.toISOString(), 'rendered', perf.count, 'words');  // log the count of the rendering process
          if (msgLevel >= 0) console.log(now.toISOString(), 'rendering process avg:', perf.avg, 'ms');  // log the average time of the rendering process      
          if (msgLevel >= 0) console.log(now.toISOString(), 'rendering process max:', perf.max, 'ms');  // log the maximum time of the rendering process     
          if (msgLevel >= 1) console.log(now.toISOString(), 'rendering process sum:', perf.sum, 'ms');  // log the sum of the times of the rendering process 
          console.log(now.toISOString(), 'clear the chat input query: "' + input.value + '"' );  // log when input field is cleared
          input.value = "";       // clear the input field
          perf.start = 0;  // reset the performance timer
          perf.end = 0;    // reset the performance timer
          perf.duration = 0;  // reset the duration of the rendering process
          perf.count = 0;  // reset the count of the rendering process
          perf.avg = 0;    // reset the average time of the rendering process
          perf.max = 0;    // reset the maximum time of the rendering process
          perf.sum = 0;    // reset the sum of the times of the rendering process
        }
        endOfTextCount++; // increment the end of text counter
        // waiting for another time interval to render the full text
        if (endOfTextCount > 3) {  // check if the end of text marker was found more than once
          if (msgLevel >= 1) console.log(now.toISOString(), 'end of text - now render the full text', endOfTextCount);  // log when end of text marker is found more than once
          // now we will render the full text
          response_fulltext = fulltext.textContent;  // get the full text
          // is it long enough to be rendered as markdown?
          if (msgLevel >= 0) console.log(now.toISOString(), 'response_fulltext.length:', response_fulltext.length);  // log the length of the full text
          if (response_fulltext.length > 0) {  // check if the full text is long enough to be rendered as markdown
            markdown.innerHTML = md.render(response_fulltext);  // render markdown to html
            endOfTextCount = 0;  // reset the end of text counter
            console.log(now.toISOString(), 'Fulltext markdown rendered to html');  // log when end of text marker is reset          
          } else {
            fulltextMissingCount++;  // increment the fulltext missing counter
            if (msgLevel >= 1) console.log(now.toISOString(), 'fulltext not found', fulltextMissingCount);  // log when fulltext is not found
          }
          if (fulltextMissingCount > 10) {  // check if the fulltext has not been found many times
              console.log(now.toISOString(), 'fulltext failed to be set by Dash callback');  
              endOfTextCount = 0;  // reset the end of text counter
              fulltextMissingCount = 0;  // reset the fulltext missing counter              
           } 
        } else {
          if (msgLevel >= 1) console.log(now.toISOString(), 'waiting for another time interval to render the full text');  // log when end of text marker is reset
        }
      // ### end of endOfText marker processing
      }
    } else {
      if (msgLevel >= 1) console.log(now.toISOString(), 'elements not found');
      fulltext = document.getElementById("results-fulltext");      // this is the element where the text is displayed
      markdown = document.getElementById("results-markdown");      // this is the element where html <= markdown is displayed
      input    = document.getElementById("human-chat-text-area");  // get the input element
    }
  }  
}

monitorBuffer();