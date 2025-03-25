/**
Copyright (C) 2020 Artem Shurshilov <shurshilov.a@yandex.ru>
Odoo Proprietary License v1.0

This software and associated files (the "Software") may only be used (executed,
modified, executed after modifications) if you have purchased a valid license
from the authors, typically via Odoo Apps, or if you have received a written
agreement from the authors of the Software (see the COPYRIGHT file).

You may develop Odoo modules that use the Software as a library (typically
by depending on it, importing it and using its resources), but without copying
any source code or material from the Software. You may distribute those
modules under the license of your choice, provided that this license is
compatible with the terms of the Odoo Proprietary License (For example:
LGPL, MIT, or proprietary licenses similar to this one).

It is forbidden to publish, distribute, sublicense, or sell copies of the Software
or modified copies of the Software.

The above copyright notice and this permission notice must be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.**/
odoo.define('swipe_images_backend', function(require) {
    var base_f = require('web.basic_fields');
    var imageWidget = base_f.FieldBinaryImage;

    var DocumentViewer = require('mail.DocumentViewer');
    var field_utils = require('web.field_utils');

    imageWidget.include({
        _render: function() {
            var self = this;
            this._super.apply(this, arguments);
            if (this.mode === 'readonly') {
                var swiper = null;
                // if set options 'swipe_field'
                if (this.attrs.options.swipe_field){
                    if (this.recordData[this.attrs.options.swipe_field]) {
                        var related = this.recordData[this.attrs.options.swipe_field];
                        var product_image_ids = this.recordData[this.attrs.options.swipe_field].data;
                        var time = new Date().getTime().toString();
                        var width = this.nodeOptions.size ? this.nodeOptions.size[0] : this.attrs.width;
                        var height = this.nodeOptions.size ? this.nodeOptions.size[1] : this.attrs.height;
                        if (!width)
                            width = 128;
                        if (!height)
                            height = 128;

                        for (var i = 0; i < product_image_ids.length; i++){
                            // base64 image data
                            var img = jQuery('<img/>', {
                                id: i.toString(),
                                'data-id': product_image_ids[i].data.id,
                                //src: 'data:image/;base64,' + product_image_ids[i].data.image,
                                src: '/web/image?model='+related.model+ "&field=image_"+width+"&id=" + JSON.stringify(product_image_ids[i].data.id) + "&unique=" + time + "#"
                            });
                            if (width) {
                                self.$el.css('width', width);
                                img.css('max-width', width + 'px');
                            }
                            if (height) {
                                self.$el.css('height', height);
                                img.css('max-height', height + 'px');
                            }
                            if(self.$el.children().length){
                                img.appendTo(self.$el.children()[0]);
                                self.$el.children().css('margin','auto');
                                img.css('margin','auto');
                            }

                        }

                        swiper = self.$el.brazzersCarousel();
                    }
                }
                // default work for product model
                else {
                    if (this.recordData.property_template_image_ids) {
                        var related = this.recordData.property_template_image_ids;
                        var product_image_ids = this.recordData.property_template_image_ids.data;
                        var time = new Date().getTime().toString();
                        var width = this.nodeOptions.size ? this.nodeOptions.size[0] : this.attrs.width;
                        var height = this.nodeOptions.size ? this.nodeOptions.size[1] : this.attrs.height;
                        if (!width)
                            width = 128;
                        if (!height)
                            height = 128;

                        for (var i = 0; i < product_image_ids.length; i++){
                            // base64 image data
                            var img = jQuery('<img/>', {
                                id: i.toString(),
                                'data-id': product_image_ids[i].data.id,
                                src: '/web/image?model='+related.model+ "&field=image_"+width+"&id=" + JSON.stringify(product_image_ids[i].data.id) + "&unique=" + time + '#'
                            });
                            if (width) {
                                self.$el.css('width', width);
                                img.css('max-width', width + 'px');
                            }
                            if (height) {
                                self.$el.css('height', height);
                                img.css('max-height', height + 'px');
                            }
                            if(self.$el.children().length){
                                img.appendTo(self.$el.children()[0]);
                                self.$el.children().css('margin','auto');
                                img.css('margin','auto');
                            }

                        }

                        swiper = self.$el.brazzersCarousel();
                    }
                }

            //swipe click handle
            if (swiper)
                swiper.parent().click(function(e) {
                    var current_div = $(this).find("div.active");
                    var all_img = $(this).closest(".brazzers-daddy").find("img");
                    var current_img = all_img.eq(current_div.index());

                    // default block preview 1 photo
                    var name_field = self.name;
                    if (name_field == "image_medium" ||
                        name_field == "image_small")
                        name_field = "image_1920";
                    // unique forces a reload of the image when the record has been updated
                    var source_id = self.model + "/" + JSON.stringify(self.res_id) + "/" + name_field + "?unique="+ field_utils.format.datetime(self.recordData.__last_update).replace(/[^0-9]/g, '')+"#";
                    var attachments = [{
                        "filename": self.recordData.display_name ,
                        "id": source_id,
                        "is_main": true,
                        "mimetype": "image/jpeg",
                        "name": self.recordData.display_name + " " + self.value,
                        "type": "image",
                    }];


                    // if from related field
                    if (self.attrs.options.swipe_field && self.recordData[self.attrs.options.swipe_field]){
                        var related = self.recordData[self.attrs.options.swipe_field];
                        var time = new Date().getTime().toString();
                        // if click non first image
                        if (current_img.data('id') >= 0 )
                            source_id =  '?model='+related.model+ "&field=image_1920&id=" + JSON.stringify(current_img.data('id')) + "&unique=" + time+"#";

                        product_image_ids = self.recordData[self.attrs.options.swipe_field].data;
                        for (var i = 0; i < product_image_ids.length; i++){
                            attachments.push({
                            "filename": i,
                            "id": '?model='+related.model+ "&field=image_1920&id=" + JSON.stringify(product_image_ids[i].data.id) + "&unique=" + time+"#",
                            "is_main": true,
                            "mimetype": "image/jpeg",
                            "name": self.attrs.options.swipe_field,
                            "type": "image",
                            });
                        }
                    }
                    // if from product
                    else {
                        if (self.recordData.property_template_image_ids){
                            //var related = self.recordData.property_template_image_ids;
                            var time = new Date().getTime().toString();
                            // if click non first image
                            if (current_img.data('id') >= 0 )
                                source_id =  "?model=product.image&field=image_1920&id=" + JSON.stringify(current_img.data('id')) + "&unique=" + time+"#";

                            product_image_ids = self.recordData.property_template_image_ids.data;
                            for (var i = 0; i < product_image_ids.length; i++){
                                attachments.push({
                                "filename": i,
                                "id": "?model=product.image&field=image_1920&id=" + JSON.stringify(product_image_ids[i].data.id) + "&unique=" + time+"#",
                                "is_main": true,
                                "mimetype": "image/jpeg",
                                "name": "product_image_ids",
                                "type": "image",
                                });
                            }
                        }
                    }

                    var attachmentViewer = new DocumentViewer(self, attachments, source_id);
                    attachmentViewer.appendTo($('body'));
                });
            }

        }
    });

});