(function($) {
    var filer_clear = function(e){
        var clearer = $(this),
            hidden_input = clearer.closest('.filerFile').find('input.vForeignKeyRawIdAdminField'),
            base_id = '#'+hidden_input.attr('id'),
            thumbnail = $(base_id+'_thumbnail_img'),
            description = $(base_id+'_description_txt'),
            static_prefix = clearer.attr('src').replace('admin/img/icon_deletelink.gif', 'filer/');
        clearer.hide();
        hidden_input.removeAttr("value");
        thumbnail.attr("src", static_prefix+"icons/nofile_48x48.png");
        description.html("");
    }

    $(document).ready(function(){
        $('.filerFile .vForeignKeyRawIdAdminField').attr('type', 'hidden');
        //if this file is included multiple time, we ensure that filer_clear is attached only once.
        $(document).off('click.filer', '.filerFile .filerClearer', filer_clear).on('click.filer', '.filerFile .filerClearer', filer_clear);
    });
})(django.jQuery);

if(window.FormData){
    (function($){
    $(document).ready(function(){

        $('.filerUploader > strong').remove();
        $('.filerUploader > span').show();
        var form = $('FORM .filerUploader').first().closest('form').get(0);
        if(typeof form.filer_uploading === 'undefined'){
            form.filer_uploading = 0 ;
            $(form).submit(function(e){
                if(this.filer_uploading > 0){
                    e.preventDefault();
                    if(this.filer_uploading == 1){
                        msg = this.filerData.msg.wait_sing;
                    }else{
                        msg = this.filerData.msg.wait_plur.replace('%(nb_files)d', this.filer_uploading);
                    }
                    alert(msg);
                }
            });
            $(document).on('click', '.filerUploader .filerChoose', function(e){
                $(this).closest('.filerUploader').find('input[type=file]').trigger('click');
            });
            $(document).on('change', '.filerUploader input[type=file]', function(e){
                var $this = $(this),
                    container = $this.closest('.filerFile'),
                    filerData = container.find('.filerChoose').data('filer'),
                    el_filename = container.find('.filerFilename'),
                    form = container.closest('form').get(0),
                    name = this.value;

                //add translations to the form.
                if(!form.filerData){form.filerData = filerData;}

                if(!name){
                    el_filename.html(filerData.msg.no_file_selected);
                }else{
                    var startIndex = (name.indexOf('\\') >= 0 ? name.lastIndexOf('\\') : name.lastIndexOf('/')),
                        url = filerData.url+'?qqfile='+name;
                    if(filerData.direct_upload_folder_key){
                        url+='&folder_key='+filerData.direct_upload_folder_key;
                    }
                    name = name.substring(startIndex+1);
                    el_filename.html(name);
                    form.filer_uploading += 1 ;
                    $.ajax({
                         url:url,
                         type: 'POST',
                         data: this.files[0],
                         cache: false,
                         dataType: 'json',
                         contentType: 'application/octet-stream',
                         processData: false,
                         context:container,
                         success: function(data, textStatus, jqXHR){
                            var base_id = '#' + this.find('.vForeignKeyRawIdAdminField').attr('id') ;
                            if(typeof data.error === 'undefined'){
                                $(base_id).attr('value', data.pk);
                                $(base_id+'_thumbnail_img').attr('src', data.thumbnail);
                                $(base_id+'_description_txt').html(data.label);
                                $(base_id+'_clear').show();
                                container.find('.filerFilename').html(filerData.msg.no_file_selected);
                            }else{
                                alert(data.error);
                            }
                            form.filer_uploading -= 1 ;
                         },
                         error: function(jqXHR, textStatus, errorThrown){
                            alert(filerData.msg.error);
                            form.filer_uploading -= 1 ;
                         },
                    });
                }
            });
        }
    });
    })(window.$ || django.jQuery);
}
